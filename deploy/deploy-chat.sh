#!/usr/bin/env bash
#
# Build the BITHub chat image, push it to ECR, and create (or update) the
# App Runner service that serves it.
#
# Run from the REPO ROOT:  ./deploy/deploy-chat.sh
#
# Prerequisites, once:
#   - deploy/Dockerfile, deploy/requirements-prod.txt in place
#   - .dockerignore at the repo root
#   - chatbot/cache/*.hdf5 present (run the service locally once to fetch it)
#   - aws CLI configured with the profile below
#   - Docker running
#
set -euo pipefail

# ── Settings ──────────────────────────────────────────────────────────────────
PROFILE=bithub-admin            # matches pipeline/deployment/OWNERSHIP.md
REGION=ap-southeast-2              # same region as the data bucket
REPO=bithub-chat
SERVICE=bithub-chat
SECRET_NAME=bithub/anthropic-api-key

# The GitHub Pages origin allowed to call this API. Origin only — scheme +
# host, no path, no trailing slash. "https://voineagulabunsw.github.io/bithub"
# is NOT an origin and will not match.
ALLOWED_ORIGINS="https://voineagulabunsw.github.io"

export AWS_PROFILE=$PROFILE AWS_REGION=$REGION

ACCOUNT=$(aws sts get-caller-identity --query Account --output text)
ECR="$ACCOUNT.dkr.ecr.$REGION.amazonaws.com"
IMAGE="$ECR/$REPO:$(git rev-parse --short HEAD)"

# ── Guard: the index must be in the build context ─────────────────────────────
# Without it the container downloads 15 MB from CloudFront on every cold start,
# and a network hiccup at boot is a crash loop rather than a slow request.
shopt -s nullglob
cache=(chatbot/cache/*.hdf5)
if [ ${#cache[@]} -eq 0 ]; then
    echo "chatbot/cache/ has no .hdf5 index." >&2
    echo "Run the backend locally once (uvicorn main:app) to fetch it, then re-run." >&2
    exit 1
fi

# ── 1. ECR repository ─────────────────────────────────────────────────────────
aws ecr describe-repositories --repository-names "$REPO" >/dev/null 2>&1 \
  || aws ecr create-repository --repository-name "$REPO" \
       --image-scanning-configuration scanOnPush=true >/dev/null

aws ecr get-login-password | docker login --username AWS --password-stdin "$ECR"

# ── 2. Build and push ─────────────────────────────────────────────────────────
# --platform is required when building on an Apple Silicon Mac: App Runner
# runs x86_64, and an arm64 image fails at container start with an exec
# format error that surfaces only in the deployment log.
#
# --provenance=false --sbom=false matter as much as --platform. Since BuildKit
# 0.11 the default build attaches a provenance attestation, which turns the
# result into a manifest LIST containing the real image plus an attestation
# entry on a synthetic "unknown/unknown" platform. Consequences seen in the
# wild: ECR's scan-on-push (enabled above) reports Failed on such images, and
# AWS services that expect a single image manifest — SageMaker CreateModel,
# Lambda, some ECS/CDK paths — reject them outright. Disabling both yields a
# plain single-platform image manifest, which every consumer understands.
#
# Equivalent if you prefer it as an env var: BUILDX_NO_DEFAULT_ATTESTATIONS=1
docker build --platform linux/amd64 \
  --provenance=false --sbom=false \
  -f deploy/Dockerfile -t "$IMAGE" .
docker push "$IMAGE"

# Confirm ECR stored ONE image manifest, not a manifest list. If this prints
# a mediaType ending in ".list.v2+json" or ".index.v1+json", the attestation
# flags above did not take effect and App Runner may fail to pull.
aws ecr batch-get-image \
  --repository-name "$REPO" \
  --image-ids imageTag="$(git rev-parse --short HEAD)" \
  --query 'images[0].imageManifestMediaType' --output text

# ── 3. Anthropic key in Secrets Manager ───────────────────────────────────────
# Never an environment variable in the service config: those are readable by
# anyone with console access to the service, and they end up in CloudFormation
# and CLI history.
if ! aws secretsmanager describe-secret --secret-id "$SECRET_NAME" >/dev/null 2>&1; then
    read -rsp "Anthropic API key (sk-ant-...): " KEY; echo
    aws secretsmanager create-secret --name "$SECRET_NAME" --secret-string "$KEY" >/dev/null
    unset KEY
fi
SECRET_ARN=$(aws secretsmanager describe-secret --secret-id "$SECRET_NAME" --query ARN --output text)

# ── 4. IAM roles ──────────────────────────────────────────────────────────────
# Two distinct roles, which is the step most likely to be missed:
#   ACCESS role  — lets App Runner PULL from ECR (build-time identity)
#   INSTANCE role — the identity the running container has; needed to READ the
#                   secret. Without it the service deploys and then fails
#                   health checks with a permissions error on the secret.
trust_build='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"build.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}'
trust_tasks='{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Service":"tasks.apprunner.amazonaws.com"},"Action":"sts:AssumeRole"}]}'

aws iam get-role --role-name AppRunnerECRAccessRole >/dev/null 2>&1 || {
    aws iam create-role --role-name AppRunnerECRAccessRole \
        --assume-role-policy-document "$trust_build" >/dev/null
    aws iam attach-role-policy --role-name AppRunnerECRAccessRole \
        --policy-arn arn:aws:iam::aws:policy/service-role/AWSAppRunnerServicePolicyForECRAccess
}

aws iam get-role --role-name BitHubChatInstanceRole >/dev/null 2>&1 || {
    aws iam create-role --role-name BitHubChatInstanceRole \
        --assume-role-policy-document "$trust_tasks" >/dev/null
    aws iam put-role-policy --role-name BitHubChatInstanceRole \
        --policy-name ReadAnthropicKey --policy-document "{
            \"Version\":\"2012-10-17\",
            \"Statement\":[{\"Effect\":\"Allow\",
                            \"Action\":\"secretsmanager:GetSecretValue\",
                            \"Resource\":\"$SECRET_ARN\"}]}"
    echo "waiting 10s for the new role to propagate"; sleep 10
}

ACCESS_ROLE=$(aws iam get-role --role-name AppRunnerECRAccessRole    --query Role.Arn --output text)
INSTANCE_ROLE=$(aws iam get-role --role-name BitHubChatInstanceRole --query Role.Arn --output text)

# ── 5. Create or update the service ───────────────────────────────────────────
# HealthCheck hits /health, which main.py serves from already-loaded objects
# (len(loader.expr) reads the HDF5 gene index, no expression bytes, no
# Anthropic call) — so probing it costs nothing.
#
# Timeout 300s: the agent loop runs up to BITHUB_MAX_TOOL_ROUNDS=10 rounds of
# Claude calls, and a multi-gene figure question genuinely takes 30-90s. The
# App Runner default of 120s would cut long answers off mid-stream and the
# frontend would surface it as a bare network error.
# Rate limits. The code defaults (main.py:66-67) are 20/hour and 200/day; these
# override them. 15/hour is tighter per visitor, 300/day is a higher ceiling
# across all visitors — set for a public launch where many people each ask a
# few questions. Both are enforced IN PROCESS, which is why MaxSize is pinned
# to 1 below.
#
# A local `docker run` with no -e flags shows 20/200, the code defaults. That
# is expected and is not what production will report.
ENVVARS="{
  \"BITHUB_ALLOWED_ORIGINS\": \"$ALLOWED_ORIGINS\",
  \"BITHUB_RATE_PER_IP_HOUR\": \"15\",
  \"BITHUB_RATE_TOTAL_DAY\": \"300\",
  \"BITHUB_MAX_TOOL_ROUNDS\": \"10\"
}"

SRC="{
  \"ImageRepository\": {
    \"ImageIdentifier\": \"$IMAGE\",
    \"ImageRepositoryType\": \"ECR\",
    \"ImageConfiguration\": {
      \"Port\": \"8000\",
      \"RuntimeEnvironmentVariables\": $ENVVARS,
      \"RuntimeEnvironmentSecrets\": {\"ANTHROPIC_API_KEY\": \"$SECRET_ARN\"}
    }
  },
  \"AutoDeploymentsEnabled\": false,
  \"AuthenticationConfiguration\": {\"AccessRoleArn\": \"$ACCESS_ROLE\"}
}"

# MaxSize=1 is a CORRECTNESS setting, not a cost one. The rate limiter in
# main.py counts hits in process memory, so N instances enforce N times the
# configured cap and the daily ceiling stops meaning anything. Raise it only
# after moving the counters to something shared (DynamoDB, ElastiCache) or
# putting WAF rate rules in front.
ASCFG=$(aws apprunner list-auto-scaling-configurations \
          --auto-scaling-configuration-name bithub-chat-single \
          --query 'AutoScalingConfigurationSummaryList[0].AutoScalingConfigurationArn' \
          --output text 2>/dev/null || true)
if [ -z "$ASCFG" ] || [ "$ASCFG" = "None" ]; then
    ASCFG=$(aws apprunner create-auto-scaling-configuration \
              --auto-scaling-configuration-name bithub-chat-single \
              --max-concurrency 20 --min-size 1 --max-size 1 \
              --query 'AutoScalingConfiguration.AutoScalingConfigurationArn' --output text)
fi

ARN=$(aws apprunner list-services \
        --query "ServiceSummaryList[?ServiceName=='$SERVICE'].ServiceArn" --output text)

if [ -z "$ARN" ]; then
    aws apprunner create-service \
      --service-name "$SERVICE" \
      --source-configuration "$SRC" \
      --auto-scaling-configuration-arn "$ASCFG" \
      --instance-configuration "{
          \"Cpu\": \"1 vCPU\", \"Memory\": \"2 GB\",
          \"InstanceRoleArn\": \"$INSTANCE_ROLE\"}" \
      --health-check-configuration '{
          "Protocol":"HTTP","Path":"/health","Interval":20,
          "Timeout":5,"HealthyThreshold":1,"UnhealthyThreshold":5}' \
      --network-configuration '{"IngressConfiguration":{"IsPubliclyAccessible":true}}' \
      --query 'Service.ServiceUrl' --output text
else
    aws apprunner update-service --service-arn "$ARN" \
      --source-configuration "$SRC" --query 'Service.ServiceUrl' --output text
fi

echo
echo "Deploying. Watch it reach RUNNING with:"
echo "  aws apprunner describe-service --service-arn \$(aws apprunner list-services \\"
echo "    --query \"ServiceSummaryList[?ServiceName=='$SERVICE'].ServiceArn\" --output text) \\"
echo "    --query 'Service.Status' --output text"

#!/usr/bin/env bash
#
# Report what AWS actually enforces for bithub-admin, as opposed to what the
# JSON files in chatbot/aws-policies/ say. Read-only: every call here is a
# List/Get/Simulate. Run it when deploy-chat.sh fails on a permission.
#
#     ./deploy-diagnose.sh
#
set -uo pipefail

PROFILE=${AWS_PROFILE:-bithub-admin}
REGION=${AWS_REGION:-ap-southeast-2}
export AWS_PROFILE=$PROFILE AWS_REGION=$REGION

ACCT=$(aws sts get-caller-identity --query Account --output text 2>/dev/null) || {
    echo "cannot call sts:GetCallerIdentity -- profile '$PROFILE' not configured?"; exit 1; }
USER_ARN="arn:aws:iam::$ACCT:user/bithub-admin"
echo "account $ACCT / region $REGION"
echo

# 1. Attached managed policies, and the DEFAULT VERSION of each. The default
#    version is what AWS enforces; editing a JSON file does not change it.
echo "── attached managed policies (v = enforced version) ──"
aws iam list-attached-user-policies --user-name bithub-admin \
    --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null | tr '\t' '\n' |
while read -r arn; do
    [ -z "$arn" ] && continue
    v=$(aws iam get-policy --policy-arn "$arn" --query 'Policy.DefaultVersionId' --output text 2>/dev/null)
    n=$(aws iam list-policy-versions --policy-arn "$arn" --query 'length(Versions)' --output text 2>/dev/null)
    printf '  %-52s %s of %s versions\n' "${arn##*/}" "$v" "$n"
done
echo
echo "── inline policies (not versioned; take effect immediately) ──"
aws iam list-user-policies --user-name bithub-admin --query 'PolicyNames' --output text 2>/dev/null |
    tr '\t' '\n' | sed 's/^/  /' || echo "  (none)"
echo

# 2. Simulate the exact calls deploy-chat.sh makes, in the order it makes them.
#    PassRole is simulated with the context key App Runner actually supplies;
#    without --context-entries a conditioned grant always reports implicitDeny,
#    which would look like a missing permission.
echo "── simulated decisions (what would happen on the next run) ──"
sim() {
  local label=$1 action=$2 resource=$3; shift 3
  local d
  d=$(aws iam simulate-principal-policy --policy-source-arn "$USER_ARN" \
        --action-names "$action" --resource-arns "$resource" "$@" \
        --query 'EvaluationResults[0].EvalDecision' --output text 2>/dev/null) \
    || d="(cannot simulate -- iam:SimulatePrincipalPolicy not granted)"
  printf '  %-34s %s\n' "$label" "$d"
}
sim "ecr:CreateRepository"        ecr:CreateRepository        "arn:aws:ecr:$REGION:$ACCT:repository/bithub-chat"
sim "secretsmanager:CreateSecret" secretsmanager:CreateSecret "arn:aws:secretsmanager:$REGION:$ACCT:secret:bithub/anthropic-api-key-??????"
sim "iam:CreateRole"              iam:CreateRole              "arn:aws:iam::$ACCT:role/BitHubChatInstanceRole"
sim "apprunner:CreateService"     apprunner:CreateService     "arn:aws:apprunner:$REGION:$ACCT:service/bithub-chat"

# PassRole is simulated BOTH ways on purpose.
#
# Passing --context-entries supplies iam:PassedToService ourselves. A policy
# whose condition requires that key then simulates as "allowed" even if the
# real caller never sends it -- and an absent key makes StringEquals evaluate
# FALSE, i.e. deny. Simulating only the with-key case is self-confirming and
# hides exactly that bug (it hid it here once already).
#
# The no-context row is the one that predicts the real CreateService call.
sim "PassRole instance (no ctx)"  iam:PassRole "arn:aws:iam::$ACCT:role/BitHubChatInstanceRole"
sim "PassRole instance (w/ ctx)"  iam:PassRole "arn:aws:iam::$ACCT:role/BitHubChatInstanceRole" \
    --context-entries 'ContextKeyName=iam:PassedToService,ContextKeyType=string,ContextKeyValues=apprunner.amazonaws.com'
sim "PassRole ecr-access (no ctx)" iam:PassRole "arn:aws:iam::$ACCT:role/AppRunnerECRAccessRole"
sim "PassRole ecr-access (w/ ctx)" iam:PassRole "arn:aws:iam::$ACCT:role/AppRunnerECRAccessRole" \
    --context-entries 'ContextKeyName=iam:PassedToService,ContextKeyType=string,ContextKeyValues=apprunner.amazonaws.com'

# ── 3. GROUND TRUTH: what does AWS actually enforce for iam:PassRole? ─────────
# Everything above is inference. This section dumps the real policy documents
# so we stop theorising. Reasoning from the error text has been wrong three
# times; this prints facts.
echo
echo "── every PassRole statement AWS actually holds for this user ──"
found=0
dump_passrole() {   # $1 = label, $2 = policy JSON document
    # No f-strings with quoted subscripts here: this source is inside a
    # single-quoted shell string, and escaping double quotes inside an f-string
    # expression is a SyntaxError. Precompute, then print with %-formatting.
    python3 -c '
import json, sys
label, doc = sys.argv[1], sys.argv[2]
try:
    d = json.loads(doc)
except Exception:
    print("  %s: (unparseable)" % label); sys.exit()
sts = d.get("Statement", [])
if isinstance(sts, dict):
    sts = [sts]
for s in sts:
    a = s.get("Action", "")
    if isinstance(a, str):
        a = [a]
    if not any(x in ("iam:PassRole", "iam:*", "*") for x in a):
        continue
    r = s.get("Resource", "")
    if isinstance(r, str):
        r = [r]
    cond = s.get("Condition")
    cond = json.dumps(cond) if cond else "none"
    print("  %s" % label)
    print("     Effect   : %s" % s.get("Effect"))
    print("     Action   : %s" % ", ".join(a))
    print("     Resource : %s" % ", ".join(r))
    print("     Condition: %s" % cond)
' "$1" "$2"
}

for arn in $(aws iam list-attached-user-policies --user-name bithub-admin \
             --query 'AttachedPolicies[].PolicyArn' --output text 2>/dev/null); do
    v=$(aws iam get-policy --policy-arn "$arn" --query 'Policy.DefaultVersionId' --output text 2>/dev/null)
    doc=$(aws iam get-policy-version --policy-arn "$arn" --version-id "$v" \
          --query 'PolicyVersion.Document' --output json 2>/dev/null)
    [ -z "$doc" ] && continue
    out=$(dump_passrole "managed ${arn##*/} ($v)" "$doc")
    [ -n "$out" ] && { echo "$out"; found=1; }
done
for n in $(aws iam list-user-policies --user-name bithub-admin --query 'PolicyNames' --output text 2>/dev/null); do
    doc=$(aws iam get-user-policy --user-name bithub-admin --policy-name "$n" \
          --query 'PolicyDocument' --output json 2>/dev/null)
    out=$(dump_passrole "inline $n" "$doc")
    [ -n "$out" ] && { echo "$out"; found=1; }
done
[ "$found" = 0 ] && echo "  NONE. No attached policy grants iam:PassRole at all."
echo

# Two things that deny despite a correct identity policy, neither of which the
# earlier version of this script checked.
echo "── permissions boundary (caps the user regardless of granted policy) ──"
pb=$(aws iam get-user --user-name bithub-admin \
     --query 'User.PermissionsBoundary.PermissionsBoundaryArn' --output text 2>/dev/null)
if [ -n "$pb" ] && [ "$pb" != "None" ]; then
    echo "  $pb"
    echo "  A boundary must ALSO allow iam:PassRole or the call is denied."
else
    echo "  none"
fi
echo
echo "── group-attached policies (also apply to this user) ──"
aws iam list-groups-for-user --user-name bithub-admin \
    --query 'Groups[].GroupName' --output text 2>/dev/null | tr '\t' '\n' |
    sed '/^$/d;s/^/  /' || true
echo

echo "allowed      -> that call will succeed"
echo "implicitDeny -> no attached policy version grants it"
echo
echo "If a PassRole row is 'allowed' with ctx but 'implicitDeny' without it, the"
echo "condition is the problem, not the grant: the policy still uses StringEquals"
echo "on iam:PassedToService, which App Runner does not send. Re-paste"
echo "aws-policies/bithub_apprunner_policy.json (StringEqualsIfExists)."

# Deploying the chat to AWS App Runner

> **The authoritative deploy lives in the `update_2` checkout**, not here:
> `Papers/BITHub/Website/update_2/bithub/deploy/deploy-chat.sh` plus
> `deploy/Dockerfile`. That script is more complete than this document — it
> creates both IAM roles, pins autoscaling to one instance, and sets the CORS
> origin. Use it. This file is kept for the IAM policies in `aws-policies/`,
> which the script needs and does not itself create.
>
> Differences from the root `Dockerfile` in this repo, which is NOT what gets
> deployed:
>
> | | root `Dockerfile` (this repo) | `deploy/Dockerfile` (deployed) |
> |---|---|---|
> | frontend | built in, served at `/` | absent — GitHub Pages serves it |
> | port | 8080 | 8000 |
> | bundle index | downloaded at boot | baked into the image |
> | instance | 0.25 vCPU / 0.5 GB | 1 vCPU / 2 GB |
>
> The API-only split is the better design for a Pages front end: the site is
> already free on Pages, and the container carries no node build. It requires
> `BITHUB_ALLOWED_ORIGINS`, which the script sets.

Container deploy of the FastAPI service as one App Runner service. Costs money
— see the cost section before starting.

This is the paid AWS path. `HOSTING.md` covers the free off-AWS options, and
`../DEPLOYMENT.md` covers the static-only GitHub Pages deploy where the chat is
hidden. Nothing here is required for the gene explorer, which works from
CloudFront alone.

## Why one container, not two

`main.py` mounts `frontend/build` at `/`, so a single service serves the site
and the API from the same origin. That is why `frontend/src/lib/config.js`
leaves `CHAT_API` empty in production builds — relative `/api/...` requests
need no CORS entry and cannot trip mixed-content blocking. Splitting the halves
into two services would reintroduce both problems for no benefit.

## Permissions

Three policies on the deploying IAM user (`bithub-admin`), each scoped to the
one resource it needs:

JSON for all three is in `aws-policies/`. Attach via **IAM → Users →
bithub-admin → Add permissions → Attach policies directly → Create policy →
JSON tab**, pasting each file whole.

| Policy (in `aws-policies/`) | Purpose | Scope |
|---|---|---|
| `bithub_deploy_policy.json` | data-bundle upload by `pipeline/main.py` | `bithub-bucket/bithub/*` |
| `bithub_ecr_policy.json` | build and push the image | repository `bithub-chat` |
| `bithub_apprunner_policy.json` | create and deploy the service | services named `bithub-*` |
| `bithub_secretsmanager_policy.json` | store and read the Anthropic key | secrets under `bithub/*` |
| `bithub_iam_roles_policy.json` | create the two roles the script needs | those two role names only |

All five are required by `deploy-chat.sh`. Attaching only some produces one
`AccessDeniedException` per missing service, in the order the script runs:
ECR, then Secrets Manager, then IAM, then App Runner.

`bithub_iam_roles_policy.json` is the one to read before attaching, because
role-management permissions deserve scrutiny. It is confined to the two role
names the script creates (`AppRunnerECRAccessRole`, `BitHubChatInstanceRole`),
grants no `DeleteRole`, and restricts `AttachRolePolicy` by condition to the
single AWS-managed ECR-access policy — so it cannot be used to attach
`AdministratorAccess` to anything.

Two grants in these use `"Resource": "*"` because AWS does not accept a
narrower scope: `ecr:GetAuthorizationToken` (the `docker login` call) and App
Runner's `List*`/`DescribeOperation` calls. Both are read-or-auth only.

No policy grants a delete action. A bug can overwrite a published object or
redeploy a service; it cannot remove either.

### `iam:PassRole` and the `PassedToService` trap

`PassRole` must cover **both** roles — `AppRunnerECRAccessRole` (pulls the
image) and `BitHubChatInstanceRole` (the container's own identity, which reads
the secret). Granting only the first fails at `create-service`.

The condition value is the part that is easy to get wrong, and I got it wrong
once here. A role has two distinct principals and they are not interchangeable:

| | value | meaning |
|---|---|---|
| trust policy `Principal` | `build.apprunner…`, `tasks.apprunner…` | who may **assume** the role |
| `iam:PassedToService` | `apprunner.amazonaws.com` | which service the role is **handed to** |

`deploy-chat.sh` correctly uses the `build.`/`tasks.` principals in the trust
policies. Copying those into `iam:PassedToService` produces a condition that
never matches, and the resulting denial names `iam:PassRole` with no hint that a
condition is responsible — it reads exactly like a missing grant.

### If `PassRole` still denies: use the unconditioned inline policy

Three separate condition theories were tried against this denial (wrong
principal value, stale policy version, absent-key semantics) and all three were
refuted — including one where `simulate-principal-policy` reported `allowed`
for the exact role and action while the real `CreateService` call still failed.
When the simulator and the API disagree, stop theorising about the condition
and remove it as a variable:

**IAM → Users → bithub-admin → Add permissions → Create inline policy → JSON**,
paste `aws-policies/bithub_passrole_inline.json`, name it `bithub-passrole-plain`.

That file grants `iam:PassRole` on the two role ARNs with **no condition at
all**. Inline is deliberate: not versioned, so there is no default version to
set and no five-version limit to hit.

This is not as loose as it sounds. `Resource` is still pinned to two specific
role ARNs — not `*` — and each role's **trust policy**, set by
`deploy-chat.sh`, only allows `build.apprunner`/`tasks.apprunner` to assume it.
Passing either role to some other service is therefore inert, because that
service could not assume it. The role scoping is the control that contains
this; the `PassedToService` condition was defence in depth on top of it.

Once the deploy succeeds, tightening back to `StringEqualsIfExists` is
optional. If you do, re-run `deploy-diagnose.sh` afterwards and check the
**no-context** `PassRole` rows still read `allowed`.

### Use `StringEqualsIfExists`, not `StringEquals`

Getting the *value* right is not sufficient. **App Runner's `CreateService`
does not populate `iam:PassedToService` for the instance role**, and IAM
evaluates a `StringEquals` condition on an **absent** key as false — so the
statement does not match and the request is implicitly denied. The error is
byte-identical to having no grant at all:

```
not authorized to perform: iam:PassRole on resource: .../BitHubChatInstanceRole
because no identity-based policy allows the iam:PassRole action
```

"no identity-based policy allows" means *implicit* deny — which is what a
non-matching condition produces. It does not mean the policy is missing.

`StringEqualsIfExists` matches when the key is absent and still constrains the
value when present, so it keeps the guardrail without depending on a key the
caller may not send.

Both `bithub_apprunner_policy.json` and `bithub_passrole_inline.json` now use
`StringEqualsIfExists`. Do not "fix" a `PassRole` denial by deleting the
condition or widening `Resource` to `*`.

`simulate-principal-policy` **will not catch this** if you pass
`--context-entries`: supplying the key yourself makes the condition match and
reports `allowed` while the real call still fails. Simulate without context
too — that is the row which predicts the real call. `deploy-diagnose.sh` now
runs both.

Unscoped `PassRole` is a privilege-escalation path — anything that can pass any
role inherits that role's permissions — so do not "fix" a denial by removing
the condition or widening `Resource` to `*`.

### Editing the JSON file does nothing

These files are source, not state. AWS enforces the **default version of the
policy attached to the user**, not anything on your disk.

If `create-service` fails on `iam:PassRole`, read the error carefully first,
because it localises the problem precisely:

`CreateService` requires **both** `apprunner:CreateService` and `iam:PassRole`,
and both grants live in `bithub_apprunner_policy.json`. A denial naming only
`iam:PassRole` therefore means `apprunner:CreateService` was **allowed** — the
policy is attached, but at an older version whose `PassRole` statement either
omits `BitHubChatInstanceRole` (v1) or carries the wrong condition (v2). If the
policy were missing entirely, the denial would name `apprunner:CreateService`
instead.

So: same error before and after editing the file means the edit did not reach
AWS. Common reasons — a new policy was created but never attached, the edit
landed on a different policy, or the managed policy already has the maximum of
five versions and the save was rejected.

**Fix that cannot fail this way:** add the grant as an **inline** policy.
Inline policies are not versioned, so there is no default version to set and no
version limit to exhaust — pasting one takes effect immediately.

**IAM → Users → bithub-admin → Add permissions → Create inline policy → JSON**,
paste `aws-policies/bithub_passrole_inline.json`, name it `bithub-passrole`,
create. It duplicates the `PassRole` grant from the managed policy, which is
harmless: identical `Allow`s do not conflict.

`./deploy-diagnose.sh` (repo root) reports all of this in one shot: which
managed policies are attached, **which version of each AWS is enforcing**, any
inline policies, and a simulated decision for every call `deploy-chat.sh`
makes. Every call it makes is a `List`/`Get`/`Simulate` — it changes nothing.

If it prints `(cannot simulate -- iam:SimulatePrincipalPolicy not granted)`,
that itself is the answer: those read-only actions are in v2 of
`bithub_iam_roles_policy.json`, so seeing that message means the v2 paste did
not reach AWS either — which is consistent with the `PassRole` denial and
points at the inline route below.

Or check the single grant by hand:

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::937485902913:user/bithub-admin \
  --action-names iam:PassRole \
  --resource-arns arn:aws:iam::937485902913:role/BitHubChatInstanceRole \
  --context-entries 'ContextKeyName=iam:PassedToService,ContextKeyType=string,ContextKeyValues=apprunner.amazonaws.com' \
  --query 'EvaluationResults[0].EvalDecision' --output text
```

`allowed` means the policy is live. `implicitDeny` means the new version is not
attached, or the condition still does not match.

## Running the deploy

`deploy-chat.sh` does all of it, idempotently: creates the ECR repo if absent,
builds and pushes, prompts once for the API key and stores it, creates both
roles, pins autoscaling to one instance, then creates or updates the service.

```bash
cd .../update_2/bithub
./deploy/deploy-chat.sh
```

It expects an `aws` profile named `bithub-admin` (`aws configure --profile
bithub-admin`), Docker running, and `chatbot/cache/*.hdf5` present — it exits
with a clear message if the index is missing, since that file gets baked into
the image.

## Two build flags that matter

`deploy-chat.sh` already passes both; they are recorded here because omitting
either produces an error that names the wrong cause.

`--platform linux/amd64` — App Runner runs amd64. An arm64 image built on an
Apple-silicon Mac fails at container start with an exec-format error visible
only in the deployment log.

`--provenance=false --sbom=false` — since BuildKit 0.11 the default build
attaches a provenance attestation, which makes the result a manifest *list*
rather than a single image. ECR's scan-on-push then reports Failed, and some
AWS services reject such images outright. The script verifies this after the
push by printing `imageManifestMediaType`: a value ending in `.list.v2+json`
or `.index.v1+json` means the flags did not take effect.

## Verify

```bash
URL=$(aws apprunner list-services \
        --query "ServiceSummaryList[?ServiceName=='bithub-chat'].ServiceUrl" \
        --output text)

curl -fsS "https://$URL/health" | python3 -m json.tool
```

Expected values, measured from the bundle index rather than assumed:

| field | expect | meaning if different |
|---|---|---|
| `data_source` | `published_bundle` | `local_files` means it found CSVs and is not reading the bundle |
| `n_genes` | `30687` | that is BrainSpan's gene count; the index holds 34440 rows but 3753 are absent from BrainSpan |
| `frontend_mounted` | `false` | **`false` is correct here** — `deploy/Dockerfile` points `BITHUB_FRONTEND_BUILD` at a nonexistent path on purpose, because Pages serves the site |

`n_genes` is per-dataset, not the index size: BrainSeq reports 34259 and GTEx
34102 from the same index. If the reported number is 34440 something is
counting index rows rather than present genes.

Then confirm CORS from the Pages origin, which is the part most likely to be
wrong and is invisible to `curl` without an Origin header:

```bash
curl -sD- -o/dev/null -X OPTIONS "https://$URL/api/chat" \
  -H "Origin: https://voineagulabunsw.github.io" \
  -H "Access-Control-Request-Method: POST" | grep -i access-control-allow-origin
```

It must echo `https://voineagulabunsw.github.io`. The origin is scheme + host
only — a value including `/bithub` will not match, and the browser failure
reads as a generic network error rather than a CORS message.

## After the service is up: point Pages at it

The deploy produces a backend; the site does not use it until the Pages build
is told where it is. Both values are inlined by Vite at **build** time, so this
requires a workflow re-run, not a setting change.

1. Get the service URL:

   ```bash
   aws apprunner list-services \
     --query "ServiceSummaryList[?ServiceName=='bithub-chat'].ServiceUrl" \
     --output text
   ```

2. In GitHub: **Settings → Secrets and variables → Actions → Variables → New
   repository variable**, name `CHAT_API_URL`, value `https://<that host>` —
   scheme and host only, no trailing slash and no path. A trailing slash breaks
   both the fetch URL and the CORS origin match.

   A *variable*, not a secret: the URL is public the moment the browser calls
   it, and secrets are masked in build logs, which makes this unreadable when
   diagnosing.

3. Re-run the **Deploy to GitHub Pages** workflow (Actions → latest run →
   Re-run all jobs), or push any commit.

`deploy.yml` derives `VITE_SHOW_CHAT` from `vars.CHAT_API_URL != ''`, so the
chat link appears only once the URL is set. Before that the site builds and
deploys exactly as it does today, with the link hidden — a visible feature that
cannot work is worse than a hidden one.

Verify the built bundle rather than the source, since these are inlined:

```bash
grep -o 'awsapprunner[^"]*' frontend/build/_app/immutable/chunks/*.js | head -1
```

Empty output after setting the variable means the workflow was not re-run.

## Cost

App Runner bills provisioned **memory continuously** — including while idle —
and vCPU only while serving requests. There is **no free tier**.

`deploy-chat.sh` provisions **1 vCPU / 2 GB**, and because `min-size` is 1 the
memory charge runs 24/7 whether or not anyone asks a question. That is the
dominant fixed cost of this deploy. Measured resident memory is ~232 MB, so
2 GB is roughly 8x headroom; dropping to 0.5 GB would cut the idle charge
substantially and still leave room. Anthropic API usage is billed separately
and may still exceed it.

`apprunner:PauseService` is in the policy for this reason: pausing stops
compute billing between demos without deleting the service or its URL. Worth
doing if the chat is only needed for specific presentations.

If the ongoing cost is unwelcome, the free options in `HOSTING.md` fit the same
232 MB footprint and need none of this IAM chain.

## Known limits

Rate limiting is in-memory (`_ip_hits`, `_day_hits` in `main.py`), so it resets
on every deploy and does not span instances. `deploy-chat.sh` pins the
autoscaling configuration to `min-size 1 max-size 1` for exactly this reason —
raising `max-size` multiplies the real cap by the instance count and makes the
daily ceiling meaningless. Treat that as a correctness setting, not a cost one.

The deployed rate limits come from the script's environment variables (15/hour
per IP, 300/day total), not the code defaults (20/hour, 200/day). A local
`docker run` with no `-e` flags reports the code defaults, which is expected
and is not what production enforces.

Uploads set a one-hour `CacheControl` and nothing issues a CloudFront
invalidation, so for up to an hour after republishing the bundle the CDN can
serve a stale `expression.bin` against a fresh `metadata.json`. That yields
plausible numbers for the wrong genes rather than an error. Wait out the hour,
or add an invalidation step — which needs a CloudFront permission not currently
granted.

The cell-type-controlled variance-partition model is not in the published
bundle. In remote mode, requesting it raises rather than silently returning the
standard model. It requires `BITHUB_LOCAL_DATA=1` and the local CSVs, so it is
unavailable in this deploy by design.

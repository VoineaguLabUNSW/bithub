#!/usr/bin/env bash
#
# Verify the deployed chat API end to end, in the order things actually break.
# Read-only against AWS; the only writes are two chat requests against your own
# service (which count toward the rate limit).
#
#     ./verify-chat.sh
#
set -uo pipefail

REGION=${AWS_REGION:-ap-southeast-2}
ORIGIN="https://voineagulabunsw.github.io"   # must match BITHUB_ALLOWED_ORIGINS
pass=0; fail=0
ok()   { printf '  \033[32mPASS\033[0m %s\n' "$1"; pass=$((pass+1)); }
bad()  { printf '  \033[31mFAIL\033[0m %s\n' "$1"; fail=$((fail+1)); }

ARN=$(aws apprunner list-services --region "$REGION" \
      --query "ServiceSummaryList[?ServiceName=='bithub-chat'].ServiceArn" --output text 2>/dev/null)
[ -z "$ARN" ] && { echo "no bithub-chat service in $REGION"; exit 1; }

# 1. Reaching RUNNING. The container downloads the index at startup, so this
#    takes a few minutes; OPERATION_IN_PROGRESS is normal, not a failure.
echo "── service status ──"
for i in $(seq 1 60); do
    ST=$(aws apprunner describe-service --service-arn "$ARN" --region "$REGION" \
         --query 'Service.Status' --output text 2>/dev/null)
    printf '\r  %s (%ds)          ' "$ST" $((i*10))
    case $ST in
        RUNNING) echo; ok "status RUNNING"; break ;;
        CREATE_FAILED|DELETE_FAILED) echo; bad "status $ST"; break ;;
    esac
    sleep 10
done
[ "${ST:-}" = RUNNING ] || {
    echo
    echo "  not RUNNING. Application logs (startup errors appear here):"
    echo "    aws logs tail /aws/apprunner/bithub-chat/*/application --region $REGION --since 15m"
    exit 1
}

URL=$(aws apprunner describe-service --service-arn "$ARN" --region "$REGION" \
      --query 'Service.ServiceUrl' --output text)
echo "  https://$URL"
echo

# 2. Health. Asserts the data actually loaded -- a 200 alone does not prove it.
echo "── /health ──"
H=$(curl -fsS --max-time 30 "https://$URL/health" 2>/dev/null)
if [ -z "$H" ]; then
    bad "/health unreachable"
else
    echo "$H" | python3 -m json.tool 2>/dev/null | sed 's/^/    /' || echo "    $H"
    python3 - "$H" <<'PY'
import json, sys
try: d = json.loads(sys.argv[1])
except Exception: print("  FAIL /health is not JSON"); sys.exit()
n = d.get("n_genes")
print("  PASS n_genes %s" % n if n == 30687 else
      "  FAIL n_genes %r (expected 30687 for BrainSpan)" % n)
src = d.get("data_source")
print("  PASS data_source %s" % src if src == "published_bundle" else
      "  FAIL data_source %r (expected published_bundle)" % src)
# frontend_mounted MUST be false here: deploy/Dockerfile is API-only and Pages
# serves the site. true would mean the wrong image got deployed.
fm = d.get("frontend_mounted")
print("  PASS frontend_mounted false (correct: Pages serves the site)"
      if fm is False else
      "  WARN frontend_mounted %r (expected false for the API-only image)" % fm)
# Which pipeline run this is reading. Two deployments can both report
# published_bundle and be serving different data.
if d.get("source_url"):
    print("  .... bundle %s" % d["source_url"])
# If a token is required, the unauthenticated POST below returns 401 and the
# failure would look like a broken service rather than a deliberate gate.
if d.get("access_token_required"):
    print("  NOTE access_token_required=true -- the chat POST below will 401")
    print("       unless BITHUB_ACCESS_TOKEN is sent; that is expected, not a fault.")
rl = d.get("rate_limit") or {}
if rl:
    print("  .... limits %s/hr per IP, %s/day total; %s used today"
          % (rl.get("per_ip_hour"), rl.get("total_day"), d.get("questions_today")))
PY
fi
echo

# 3. CORS. The check most likely to fail and the one curl hides: without an
#    Origin header the server never emits the header the browser requires, so
#    a plain curl passes while the site is broken.
echo "── CORS preflight from $ORIGIN ──"
PF=$(curl -sS -X OPTIONS --max-time 20 \
     -H "Origin: $ORIGIN" \
     -H "Access-Control-Request-Method: POST" \
     -H "Access-Control-Request-Headers: content-type" \
     -D - -o /dev/null "https://$URL/api/chat" 2>/dev/null)
AO=$(printf '%s' "$PF" | tr -d '\r' | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}')
if [ "$AO" = "$ORIGIN" ] || [ "$AO" = "*" ]; then
    ok "allow-origin: $AO"
else
    bad "allow-origin missing or wrong (got '${AO:-none}')"
    echo "     BITHUB_ALLOWED_ORIGINS must equal $ORIGIN exactly --"
    echo "     scheme+host only, no trailing slash, no /bithub path."
fi
echo

# 4. A real chat round trip, in the exact body shape stores/chat.js sends.
echo "── POST /api/chat (real request shape) ──"
R=$(curl -sS --max-time 120 -X POST "https://$URL/api/chat" \
    -H "Origin: $ORIGIN" -H 'Content-Type: application/json' \
    -d '{"message":"What is the expression of SOX2 in BrainSpan?","history":[],"datasets":["BrainSpan"]}' \
    2>/dev/null)
if [ -z "$R" ]; then
    bad "no response (ANTHROPIC_API_KEY unreadable from Secrets Manager?)"
else
    python3 - "$R" <<'PY'
import json, sys
raw = sys.argv[1]
try: d = json.loads(raw)
except Exception:
    print("  FAIL non-JSON response:"); print("   ", raw[:300]); sys.exit()
# FastAPI puts HTTPException messages in "detail" -- that is the field
# stores/chat.js reads on !res.ok, so check the same one.
if d.get("detail"):
    det = str(d["detail"])
    print("  FAIL %s" % det[:300])
    low = det.lower()
    if "token" in low:
        print("       an access token is configured; not a deployment fault")
    elif "rate" in low or "limit" in low:
        print("       rate limited; the service itself is working")
    elif "key" in low or "credential" in low or "anthropic" in low:
        print("       the instance role cannot read the secret. Check:")
        print("       aws secretsmanager get-secret-value --secret-id bithub/anthropic-api-key")
    sys.exit()
# stores/chat.js reads body.response -- assert that exact field, not a guess.
txt = d.get("response")
if txt:
    print("  PASS response %d chars" % len(txt))
    print("    %s..." % " ".join(str(txt).split())[:180])
    print("  .... figures=%d tables=%d" % (len(d.get("figures") or []),
                                           len(d.get("tables") or [])))
else:
    print("  FAIL no 'response' field (the one the frontend reads); keys: %s" % list(d))
PY
fi
echo
echo "── $pass passed, $fail failed ──"
[ "$fail" -eq 0 ] && cat <<EOF

Backend verified. Last step -- point the site at it:
  1. GitHub -> Settings -> Secrets and variables -> Actions -> Variables
     New repository variable: CHAT_API_URL = https://$URL
     (no trailing slash)
  2. Actions -> "Deploy to GitHub Pages" -> Re-run all jobs
     Vite inlines this at build time, so setting the variable alone does nothing.
EOF
exit $((fail > 0))

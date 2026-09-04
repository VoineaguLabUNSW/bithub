#!/usr/bin/env bash
# Share the BITHub demo over an ngrok tunnel, with an access key.
#
# Anything on a public URL that calls the Anthropic API is spending real money
# for whoever finds it, and ngrok subdomains get scanned. So this script will
# not start without a key: it generates one, prints the link with the key
# embedded, and the backend rejects /api/chat requests that lack it.
#
# The key is a shared secret for a temporary link, not authentication. Anyone
# you send it to can spend credits. Stop the tunnel when you are done.
set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8000}"
command -v ngrok >/dev/null || { echo "ngrok not found — brew install ngrok"; exit 1; }

export BITHUB_ACCESS_TOKEN="${BITHUB_ACCESS_TOKEN:-$(python3 -c 'import secrets;print(secrets.token_urlsafe(12))')}"
export BITHUB_RATE_PER_IP_HOUR="${BITHUB_RATE_PER_IP_HOUR:-20}"
export BITHUB_RATE_TOTAL_DAY="${BITHUB_RATE_TOTAL_DAY:-200}"

echo "==> Building frontend"
cd frontend
[ -d node_modules ] || npm install --legacy-peer-deps
VITE_SHOW_CHAT=true npm run build >/dev/null
cd ..

echo "==> Starting backend on :${PORT}"
( cd chatbot && .venv/bin/uvicorn main:app --port "${PORT}" ) &
BACKEND=$!
trap 'kill $BACKEND 2>/dev/null || true' EXIT

for _ in $(seq 1 40); do
  sleep 1
  curl -sf -m 2 "http://127.0.0.1:${PORT}/api/health" >/dev/null && break
done

echo "==> Opening tunnel"
ngrok http "${PORT}" --log stdout >/tmp/bithub_ngrok.log 2>&1 &
NGROK=$!
trap 'kill $BACKEND $NGROK 2>/dev/null || true' EXIT

URL=""
for _ in $(seq 1 30); do
  sleep 1
  URL=$(curl -s http://127.0.0.1:4040/api/tunnels 2>/dev/null \
        | python3 -c 'import sys,json;d=json.load(sys.stdin);print(d["tunnels"][0]["public_url"])' 2>/dev/null || true)
  [ -n "$URL" ] && break
done
[ -n "$URL" ] || { echo "Could not read the ngrok URL — check /tmp/bithub_ngrok.log"; exit 1; }

cat <<MSG

  Share this link:

    ${URL}/ask?k=${BITHUB_ACCESS_TOKEN}

  The key is consumed on first load and kept for that browser tab only.
  Limits: ${BITHUB_RATE_PER_IP_HOUR}/hour per visitor, ${BITHUB_RATE_TOTAL_DAY}/day total.
  Ctrl-C stops both the tunnel and the backend.

MSG
wait $BACKEND


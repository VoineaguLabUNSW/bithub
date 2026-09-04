#!/usr/bin/env bash
# One-command BITHub + Ask BITHub.
#
# Builds the site with the chat entry point enabled, then serves the whole
# thing — pages and API — from the single FastAPI process on port 8000.
# Same origin, so no CORS and no second terminal.
#
# DATA SOURCE — the published bundle, same as the website.
#
# Both halves resolve data the same way: take a metadata.json URL, read
# out.hdf5 and expression.bin as siblings of it. Unset, both use the site's
# CloudFront default, so the chat answers from exactly what the page plots.
# That is the intended way to run this and needs no configuration.
#
#   ./demo.sh              the live site's published bundle
#   PORT=8010 ./demo.sh    different port
#
# SOURCE=<url-or-path> overrides it. Only do that to test a staging
# distribution before it goes live — the pipeline/output copy on this machine
# is a DIFFERENT pipeline run from the published one (HDBR regions read
# "Choroid plexus" published vs "Chroid plexus" locally), so a chat pointed
# there disagrees with the site's own figures. The backend prints a warning
# at startup, /api/health reports the resolved source, and the /ask header
# flags a mismatch between the two halves.
#
# This is for demos and local review. Production keeps the frontend on
# S3/CloudFront and the API behind its own URL with rate limiting.
set -euo pipefail
cd "$(dirname "$0")"
ROOT="$PWD"

PORT="${PORT:-8000}"

if [ ! -f chatbot/.env ] && [ -z "${ANTHROPIC_API_KEY:-}" ]; then
  echo "error: no API key. Either create chatbot/.env with"
  echo "    ANTHROPIC_API_KEY=sk-ant-..."
  echo "  or export ANTHROPIC_API_KEY before running this." >&2
  exit 1
fi

echo "==> Building frontend (chat entry point enabled)"
cd frontend
[ -d node_modules ] || npm install --legacy-peer-deps
VITE_CHAT_API= VITE_SHOW_CHAT=true npm run build

cd ../chatbot
if [ -n "${SOURCE:-}" ]; then
  # Relative paths are resolved against the repo root, not chatbot/, so
  # `SOURCE=pipeline/output` means what it looks like from where you typed it.
  case "$SOURCE" in
    http://*|https://*|file://*|/*) export BITHUB_SOURCE="$SOURCE" ;;
    *)                              export BITHUB_SOURCE="$ROOT/$SOURCE" ;;
  esac
  echo "==> Data source OVERRIDDEN: $BITHUB_SOURCE"
  echo "    (not the published bundle — see the note at the top of this script)"
else
  echo "==> Data source: the site's published bundle (8 datasets)"
  echo "    first run downloads a 15 MB index into chatbot/cache/"
fi

echo "==> Starting BITHub on http://localhost:${PORT}"
echo "    site   http://localhost:${PORT}/"
echo "    chat   http://localhost:${PORT}/ask"
exec .venv/bin/uvicorn main:app --port "${PORT}"

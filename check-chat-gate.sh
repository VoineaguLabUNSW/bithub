#!/usr/bin/env bash
# Is the "Ask BITHub" button present in the DEPLOYED bundle?
#
# The two constants that decide this are inlined by Vite at build time into
# _app/immutable/chunks/config.<hash>.js, as the last line of that file:
#
#     const b="<CHAT_API>",L=<!0|!1>;export{b as C,A as L,L as S};
#
# L=!0 is true (button renders); L=!1 is false (button compiled out, markup
# present but unreachable). No amount of reloading changes a built bundle.
#
# The config chunk is NOT named in the homepage HTML — grepping index.html for
# it finds nothing. It is imported by the homepage's node chunk, so this script
# walks the chain: index.html -> entry/app -> nodes/2 -> chunks/config.
set -euo pipefail

BASE="${1:-https://voineagulabunsw.github.io/bithub}"
T=$(mktemp -d)
trap 'rm -rf "$T"' EXIT

fetch() { curl -fsS --max-time 25 -H 'Cache-Control: no-cache' "$1" -o "$2"; }

# Cache-bust the HTML: Pages sets a short max-age, but a stale copy here would
# send us to the previous build's chunks and silently report the old answer.
fetch "$BASE/?cb=$RANDOM" "$T/index.html"

APP=$(grep -oE 'entry/app\.[A-Za-z0-9_-]+\.js' "$T/index.html" | head -1)
[ -n "$APP" ] || { echo "FAIL could not find the app chunk in $BASE/"; exit 1; }
fetch "$BASE/_app/immutable/$APP" "$T/app.js"

# nodes/2 is the homepage route component; it imports the config chunk.
N2=$(grep -oE 'nodes/2\.[A-Za-z0-9_-]+\.js' "$T/app.js" | head -1)
[ -n "$N2" ] || { echo "FAIL could not find the homepage node chunk"; exit 1; }
fetch "$BASE/_app/immutable/$N2" "$T/n2.js"

CFG=$(grep -oE 'chunks/config\.[A-Za-z0-9_-]+\.js' "$T/n2.js" | head -1)
[ -n "$CFG" ] || { echo "FAIL could not find the config chunk"; exit 1; }
fetch "$BASE/_app/immutable/$CFG" "$T/config.js"

echo "build:  $APP"
echo "config: $CFG"
echo

python3 - "$T/config.js" <<'PY'
import re, sys
s = open(sys.argv[1]).read()
# Match the export by shape, not by identifier: the minified names are
# rollup-assigned and change between builds.
m = re.search(r'const\s+\w+="([^"]*)",\w+=(!0|!1);export', s)
if not m:
    print("FAIL could not parse the config chunk; last 200 chars:")
    print("  " + s[-200:])
    sys.exit(1)
api, show = m.group(1), m.group(2) == "!0"
print("  CHAT_API  = %s" % (repr(api) if api else "'' (empty)"))
print("  SHOW_CHAT = %s" % show)
print()
if show and api:
    print("  PASS the button renders and points at a backend.")
elif show and not api:
    print("  FAIL button renders but CHAT_API is empty: it will POST to")
    print("       github.io/api/chat and 404. VITE_CHAT_API did not reach the build.")
    sys.exit(1)
else:
    print("  FAIL the button is compiled out of this build (SHOW_CHAT false).")
    print("       VITE_SHOW_CHAT was not the string 'true' when Vite ran.")
    print("       This is a build-time value: reloading cannot change it.")
    sys.exit(1)
PY

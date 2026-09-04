#!/usr/bin/env python3
"""
Serve pipeline/output over HTTP with Range + CORS, for local site development.

The site streams single gene rows out of a 3.3 GB expression.bin using HTTP
Range requests, and core.js hard-fails on anything that is not a 206:

    if (response.status !== 206) ... 'Invalid response, 206 expected'

Python's stdlib SimpleHTTPRequestHandler ignores Range and answers 200, so it
cannot serve this site — hence this script.

Usage, from the repo root:

    python3 tools/serve_pipeline.py                 # port 5501, ./pipeline/output
    PORT=5502 python3 tools/serve_pipeline.py
    python3 tools/serve_pipeline.py /other/dir

Pairs with frontend/static/metadata.json when its urls point at
http://localhost:5501/pipeline/output/... — note the path prefix is part of
those urls, so this server mounts the directory at /pipeline/output/.

Development only: binds loopback, serves one directory read-only, no auth.
"""
from __future__ import annotations

import os
import re
import sys
from functools import partial
from http import HTTPStatus
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path

# metadata.json urls are http://localhost:PORT/pipeline/output/<file>, so the
# served directory has to appear under that prefix.
URL_PREFIX = "/pipeline/output"

RANGE_RE = re.compile(r"^bytes=(\d*)-(\d*)$")
CHUNK = 1 << 20  # 1 MiB


class RangeHandler(SimpleHTTPRequestHandler):
    """Static handler with byte-range support and permissive CORS."""

    protocol_version = "HTTP/1.1"  # required for keep-alive + ranged streaming

    # ── CORS ──────────────────────────────────────────────────────────────
    def end_headers(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Expose-Headers", "Content-Range, Content-Length")
        self.send_header("Accept-Ranges", "bytes")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Range, Content-Type")
        self.send_header("Content-Length", "0")
        self.end_headers()

    # ── path mapping: strip the /pipeline/output prefix ────────────────────
    def translate_path(self, path):
        clean = path.split("?", 1)[0].split("#", 1)[0]
        if clean.startswith(URL_PREFIX):
            path = clean[len(URL_PREFIX):] or "/"
        return super().translate_path(path)

    # ── ranged GET ────────────────────────────────────────────────────────
    def do_GET(self):
        header = self.headers.get("Range")
        if not header:
            return super().do_GET()

        m = RANGE_RE.match(header.strip())
        if not m:
            self.send_error(HTTPStatus.BAD_REQUEST, "Malformed Range")
            return

        target = Path(self.translate_path(self.path))
        if not target.is_file():
            self.send_error(HTTPStatus.NOT_FOUND, "File not found")
            return

        size = target.stat().st_size
        first, last = m.group(1), m.group(2)

        if first == "":                      # suffix range: bytes=-N (last N bytes)
            if last == "":
                self.send_error(HTTPStatus.BAD_REQUEST, "Malformed Range")
                return
            length = min(int(last), size)
            start, end = size - length, size - 1
        else:
            start = int(first)
            end = int(last) if last else size - 1
            end = min(end, size - 1)

        if start >= size or start > end:
            self.send_response(HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE)
            self.send_header("Content-Range", f"bytes */{size}")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        length = end - start + 1
        self.send_response(HTTPStatus.PARTIAL_CONTENT)          # 206
        self.send_header("Content-Type", self.guess_type(str(target)))
        self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
        self.send_header("Content-Length", str(length))
        self.end_headers()

        with open(target, "rb") as fh:
            fh.seek(start)
            remaining = length
            while remaining > 0:
                buf = fh.read(min(CHUNK, remaining))
                if not buf:
                    break
                try:
                    self.wfile.write(buf)
                except (BrokenPipeError, ConnectionResetError):
                    return  # browser aborted the stream; normal when panning genes
                remaining -= len(buf)

    def log_message(self, fmt, *args):
        rng = self.headers.get("Range")
        suffix = f"  Range: {rng}" if rng else ""
        sys.stderr.write(f"{self.address_string()} - {fmt % args}{suffix}\n")


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else "pipeline/output").resolve()
    port = int(os.environ.get("PORT", "5501"))

    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        print("run from the repo root, or pass the path explicitly", file=sys.stderr)
        return 1

    expected = ["metadata.json", "out.hdf5", "expression.bin"]
    missing = [f for f in expected if not (root / f).exists()]

    print(f"serving {root}")
    print(f"        http://localhost:{port}{URL_PREFIX}/")
    for f in expected:
        p = root / f
        mark = f"{p.stat().st_size / 1e6:,.1f} MB" if p.exists() else "MISSING"
        print(f"        {f:18} {mark}")
    if missing:
        print(f"warning: missing {', '.join(missing)} — the site will fail to load",
              file=sys.stderr)

    handler = partial(RangeHandler, directory=str(root))
    httpd = HTTPServer(("127.0.0.1", port), handler)
    print("ctrl-c to stop")
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())

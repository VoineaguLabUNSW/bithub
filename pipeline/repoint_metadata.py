#!/usr/bin/env python3
"""Rewrite pipeline/output/metadata.json to point at a CloudFront distribution.

The pipeline is run with `deploy_local: True`, which writes localhost URLs into
metadata.json. This script converts them to CloudFront URLs without re-running
anything. Use it INSTEAD of `deploy_local: False`, which uploads to a
hardcoded bucket (main.py:45/49 ignore `deploy_bucket`).

Usage:
    python3 repoint_metadata.py dXXXXXXXXXXXXX.cloudfront.net

Writes output/metadata.json.new; it never overwrites in place. Diff, then move.
"""
import json
import re
import sys
from pathlib import Path

LOCAL_RE = re.compile(r"^https?://localhost(:\d+)?/.*/(?P<name>[^/]+)$")
URL_KEYS = ("data_url", "bin_url")
ENTRY_KEYS = ("meta_url", "matrix_url")


def convert(url: str, cf_host: str, prefix: str = "bithub") -> str:
    """localhost URL -> CloudFront URL, keyed on basename only."""
    m = LOCAL_RE.match(url)
    if not m:
        if url.startswith(f"https://{cf_host}/"):
            return url          # already converted; idempotent
        raise ValueError(f"unrecognised URL, refusing to guess: {url!r}")
    return f"https://{cf_host}/{prefix}/{m.group('name')}"


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    cf_host = sys.argv[1].strip().rstrip("/")
    if cf_host.startswith("http"):
        print(f"error: pass the bare hostname, not a URL: {cf_host}")
        return 2
    if not cf_host.endswith(".cloudfront.net"):
        print(f"warning: {cf_host!r} does not look like a CloudFront hostname")

    src = Path(__file__).parent / "output" / "metadata.json"
    dst = src.with_suffix(".json.new")
    meta = json.loads(src.read_text())

    changed = []
    for k in URL_KEYS:
        old = meta[k]
        meta[k] = convert(old, cf_host)
        changed.append((k, old, meta[k]))

    for entry in meta["meta_files"]:
        for k in ENTRY_KEYS:
            if k in entry:
                old = entry[k]
                entry[k] = convert(old, cf_host)
                changed.append((f"{entry['name']}.{k}", old, entry[k]))

    # Fail loudly rather than shipping a half-converted file.
    blob = json.dumps(meta)
    for bad in ("localhost", "127.0.0.1", "file://"):
        if bad in blob:
            print(f"error: {bad!r} still present after conversion; not writing")
            return 1

    dst.write_text(json.dumps(meta, indent=4) + "\n")

    print(f"rewrote {len(changed)} URLs -> {dst}")
    print(f"  datasets      : {len(meta['meta_files'])}")
    print(f"  gene count    : {meta.get('count')}")
    print(f"  last_updated  : {meta.get('last_updated')}")
    print("\nsample conversions:")
    for name, old, new in changed[:3]:
        print(f"  {name}\n    {old}\n -> {new}")
    print(f"\nNext: diff against the live site's copy, then")
    print(f"  cp {dst} ../frontend/static/metadata.json")
    return 0


if __name__ == "__main__":
    sys.exit(main())

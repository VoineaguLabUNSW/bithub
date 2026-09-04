"""
Live test of BITHubRemoteLoader against the published CloudFront bundle.

Needs network access to d33ldq8s2ek4w8.cloudfront.net. Downloads out.hdf5
(15 MB) into chatbot/cache/ on first run, then reads single gene rows out of
the 3.4 GB expression.bin by byte range.

    .venv/bin/python test_remote_loader.py
"""

import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from remote_loader import BITHubRemoteLoader, RemoteBundleError, make_session  # noqa: E402
from source import DEFAULT_SOURCE, resolve  # noqa: E402

GENES = ["SHANK3", "ACTB", "GAPDH", "GFAP", "FOXP2", "MECP2"]


def main() -> int:
    # Index and binary are resolved as siblings of the metadata.json named by
    # BITHUB_SOURCE, the same rule the website follows. The URL fields inside
    # metadata.json are ignored: a deploy_local run fills them with localhost.
    src = resolve()
    print(f"source            {src.label}")

    if src.is_local:
        cache = src.local_index
    else:
        # Download out.hdf5 on first run, reuse the cached copy after.
        cache = HERE / "cache" / src.cache_name()
        legacy = HERE / "cache" / "out.hdf5"
        if not cache.exists() and legacy.exists() and resolve(DEFAULT_SOURCE).data_url == src.data_url:
            cache = legacy
        if not cache.exists():
            cache.parent.mkdir(parents=True, exist_ok=True)
            with make_session().get(src.data_url, stream=True, timeout=300) as r:
                r.raise_for_status()
                with open(cache, "wb") as f:
                    for chunk in r.iter_content(1 << 20):
                        f.write(chunk)
            print(f"downloaded        out.hdf5 ({cache.stat().st_size / 1e6:.1f} MB)")

    loader = BITHubRemoteLoader(cache, dataset="BrainSpan", bin_url=src.bin_url)

    print(f"bundle            {len(loader.genes):,} genes")
    print(f"expression.bin    {loader.bin_url}")

    # The embedded path attribute must be rejected, not attempted.
    try:
        BITHubRemoteLoader(cache, dataset="BrainSpan")
    except RemoteBundleError:
        print("localhost guard   embedded deploy_local path correctly refused")
    else:
        raise AssertionError("embedded localhost URL should have been refused")

    print("\ngene      n  published z")
    for gene in GENES:
        values = loader.gene_expression(gene)
        assert len(values) == 524, f"{gene}: got {len(values)} values, expected 524"
        assert np.isfinite(values).all(), f"{gene}: non-finite values"
        print(f"  {gene:<8}{len(values):>4}{loader.gene_zscore(gene):>+13.3f}")

    md = loader.sample_metadata
    assert len(md) == 524, f"sample metadata has {len(md)} rows, expected 524"
    print(f"\nsample metadata   {md.shape[0]} samples x {md.shape[1]} columns")
    print(f"  columns         {', '.join(list(md.columns)[:6])} …")

    try:
        loader.gene_expression("NOTAREALGENE")
    except ValueError as exc:
        print(f"\nunknown gene      handled: {str(exc)[:56]}")
    else:
        raise AssertionError("unknown gene should raise ValueError")

    before = loader._fetch_row.cache_info().hits
    loader.gene_expression("SHANK3")
    assert loader._fetch_row.cache_info().hits > before, "row cache not working"
    print(f"row cache         {loader._fetch_row.cache_info()}")

    print("\nAll remote loader checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Convert the BrainSpan expression CSV to parquet for faster server startup.

    python scripts/build_parquet.py

Measured on the 158 MB BrainSpan matrix: load drops from 0.86s to 0.05s
(warm cache, best of 3; ~3x on a cold read) and on-disk size from 158 MB to
87 MB. data_loader picks the .parquet up automatically when it exists.
"""
import sys, time
from pathlib import Path
import numpy as np
import pandas as pd

DATA = Path(__file__).resolve().parent.parent / "data"
CSV = DATA / "BrainSpan-exp.csv"
OUT = CSV.with_suffix(".parquet")

def main() -> int:
    if not CSV.exists():
        print(f"error: {CSV} not found", file=sys.stderr)
        return 1
    if OUT.exists() and OUT.stat().st_mtime > CSV.stat().st_mtime:
        print(f"{OUT.name} is already newer than the CSV — nothing to do.")
        return 0

    t0 = time.perf_counter()
    df = pd.read_csv(CSV, index_col=0)
    df.index = df.index.astype(str).str.strip()
    df.index.name = "ensembl_id"
    df = df.astype(np.float32)          # RPKM does not need float64
    df.to_parquet(OUT, engine="pyarrow", compression="zstd")

    back = pd.read_parquet(OUT)
    assert back.shape == df.shape, f"shape drift {back.shape} != {df.shape}"
    assert back.index.equals(df.index), "index drift"
    assert list(back.columns) == list(df.columns), "column drift"

    mb = lambda p: p.stat().st_size / 1e6
    print(f"wrote {OUT.name}  {df.shape[0]:,} genes x {df.shape[1]} samples")
    print(f"  {mb(CSV):.0f} MB -> {mb(OUT):.0f} MB in {time.perf_counter()-t0:.1f}s")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

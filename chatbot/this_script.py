"""
Print the raw headers of each data file.

Useful when a new export arrives and you need to check whether the column
names still match METADATA_COLUMNS in data_loader.py.

    .venv/bin/python this_script.py
"""

from pathlib import Path

import pandas as pd

DATA = Path(__file__).resolve().parent / "data"

FILES = [
    ("expression",          "BrainSpan-exp.csv",                 True),
    ("metadata",            "BrainSpan-metadata.csv",            True),
    ("varPart",             "BrainSpan_varPart.csv",             True),
    ("varPart cell types",  "BrainSpan_varPart_cellTypes.csv",   True),
    ("gene annotation",     "gene_annotation.csv",               False),
]

for label, name, indexed in FILES:
    path = DATA / name
    print(f"\n=== {label} — {name} ===")
    if not path.exists():
        print("  MISSING")
        continue
    df = pd.read_csv(path, index_col=0 if indexed else None, nrows=3)
    print(f"  columns ({len(df.columns)}): {df.columns.tolist()[:8]}")
    if indexed:
        print(f"  index: {df.index[:3].tolist()}")
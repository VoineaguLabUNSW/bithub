#!/usr/bin/env python3
"""Which dataset has zero overlap between matrix columns and metadata samples?

main.py crashes with:
    ValueError: All chunk dimensions must be positive

That happens in write_metadata_columns when a metadata column has ZERO rows.
A column is emptied when the sample whitelist is empty, and the whitelist is:

    sample_whitelist = samples_from_matrices INTERSECT samples_from_metadata
                       (main.py:648)

i.e. the matrix's column headers and the metadata's first column share no
values. Usually a naming-convention mismatch, not missing data.

Run from pipeline/:   python check_samples.py input.yaml
Reads only; changes nothing.
"""
import sys, os, csv, itertools

try:
    import oyaml as yaml
except ImportError:
    import yaml


def iterate_csv_headers(path, strip_numeric):
    """Replicates main.py's iterate_csv header handling."""
    with open(path, newline='', errors='replace') as f:
        rows = csv.reader(f)
        headers = next(rows)
        second = next(rows, None)
        if second is None:
            return [], []
        if len(headers) == len(second):
            headers = headers[1:]
        offset = 2 if second[0].isdigit() and strip_numeric else 1
        headers = headers[offset - 1:]
        return headers, second


def first_column(path):
    """Sample ids = first real column of the metadata CSV, same rule as main.py."""
    with open(path, newline='', errors='replace') as f:
        rows = csv.reader(f)
        headers = next(rows)
        second = next(rows, None)
        if second is None:
            return []
        offset = 2 if second[0].isdigit() else 1
        out = [second[offset - 1]]
        out += [r[offset - 1] for r in rows if len(r) >= offset]
        return out


cfg = yaml.safe_load(open(sys.argv[1] if len(sys.argv) > 1 else 'input.yaml'))
bad = 0

for d in cfg['datasets']:
    did, ddir = d['id'], d.get('dir', '')
    mpath = os.path.join(ddir, d['meta'])
    if not os.path.exists(mpath):
        print(f"{did:<14} metadata not found: {mpath}")
        bad += 1
        continue

    meta_samples = first_column(mpath)
    meta_set = set(meta_samples)

    for m in d['matrices']:
        xpath = os.path.join(ddir, m['path'])
        if not os.path.exists(xpath):
            print(f"{did:<14} matrix not found: {xpath}")
            bad += 1
            continue

        cols, row2 = iterate_csv_headers(xpath, strip_numeric=True)
        # first field of a stripped row is the gene key, the rest are samples
        matrix_samples = set(cols)
        overlap = matrix_samples & meta_set

        status = "OK" if overlap else "*** ZERO OVERLAP -> this is the crash ***"
        print(f"{did:<14} matrix cols={len(matrix_samples):<7} "
              f"metadata rows={len(meta_set):<7} shared={len(overlap):<7} {status}")

        if not overlap:
            bad += 1
            print(f"    matrix column names look like : {sorted(matrix_samples)[:3]}")
            print(f"    metadata sample ids look like : {sorted(meta_set)[:3]}")
            print(f"    gene key column               : {row2[0]!r}")
        elif len(overlap) < len(meta_set):
            dropped = len(meta_set) - len(overlap)
            print(f"    note: {dropped} metadata sample(s) not present in the matrix; "
                  f"they are silently dropped")

print()
print("no zero-overlap datasets" if bad == 0 else f"{bad} problem(s) — fix these before re-running main.py")

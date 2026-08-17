#!/usr/bin/env python3

import sys, os, csv, itertools

try:
    import oyaml as yaml
except ImportError:
    try:
        import yaml
    except ImportError:
        sys.exit("need PyYAML or oyaml: pip install oyaml")
        

ERRORS, WARNINGS = [], []
def err(m): ERRORS.append(m)
def warn(m): WARNINGS.append(m)

def header_of(path):
    """First CSV row, quotes and whitespace stripped."""
    with open(path, newline='', errors='replace') as f:
        return [c.strip().strip('"').strip() for c in next(csv.reader(f))]

def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    skip_paths = '--skip-paths' in sys.argv
    if not args:
        sys.exit(__doc__)
    cfg_path = args[0]
    cfg = yaml.safe_load(open(cfg_path))

    # ---- unfilled placeholders -------------------------------------------
    raw = open(cfg_path).read()
    n_fill = raw.count('<<<FILL')
    if n_fill:
        warn(f"{n_fill} unfilled <<<FILL>>> placeholder(s) — path checks will fail until replaced")

    # ---- top-level keys ---------------------------------------------------
    if 'groups' not in cfg:
        err("no `groups:` key. main.py:836 reads inputObj['groups'] and will "
            "raise KeyError AFTER the full gene loop. If you have `panels:`, "
            "rename it to `groups:` and each entry's `name:` to `id:`.")
    if 'panels' in cfg:
        err("`panels:` is present but main.py never reads it — rename to `groups:`.")
    for k in ('output_resources', 'output_external', 'ncbi_gtf',
              'ncbi_gene_info', 'genenames_alias', 'datasets'):
        if k not in cfg:
            err(f"missing required top-level key `{k}`")

    datasets = cfg.get('datasets', [])
    ids = [d.get('id') for d in datasets]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        err(f"duplicate dataset id(s): {sorted(dupes)}")
    print(f"config: {cfg_path}")
    print(f"datasets: {len(datasets)} -> {', '.join(str(i) for i in ids)}\n")

    # ---- annotation files -------------------------------------------------
    if not skip_paths:
        for k in ('ncbi_gtf', 'ncbi_gene_info', 'genenames_alias'):
            p = cfg.get(k)
            if p and not os.path.exists(p):
                err(f"{k}: not found -> {p}")
        gn = cfg.get('genenames_alias')
        if gn and os.path.exists(gn):
            expected = ['HGNC ID', 'Approved symbol', 'Status',
                        'Previous symbols', 'Alias symbols', 'Ensembl gene ID']
            actual = open(gn, encoding='utf8').readline().rstrip('\r\n').split('\t')
            if actual != expected:
                err(f"genenames.tsv column order is wrong — main.py reads it "
                    f"positionally (row[1],row[3],row[4],row[5]).\n"
                    f"        expected: {expected}\n        actual:   {actual}")

    # ---- per dataset ------------------------------------------------------
    meta_headers = {}
    for d in datasets:
        did, ddir = d.get('id'), d.get('dir', '')
        if not did:
            err("a dataset entry has no `id`"); continue
        if not d.get('matrices'):
            err(f"[{did}] no `matrices` — main.py requires at least one")

        for key in ('meta', 'annot', 'variancePartition'):
            rel = d.get(key)
            if not rel:
                continue
            p = os.path.join(ddir, rel)
            if skip_paths or '<<<FILL' in str(rel) or '<<<FILL' in str(ddir):
                continue
            if not os.path.exists(p):
                err(f"[{did}] {key}: not found -> {p}"); continue

            if key == 'meta':
                meta_headers[did] = header_of(p)
            if key == 'annot':
                if 'annot-final' in os.path.basename(p):
                    err(f"[{did}] annot points at an *-annot-final.csv. Those are "
                        f"5-column R exports; main.py requires exactly 4 "
                        f"(`len(row)==4 and row[2]=='Yes'`), so EVERY row fails "
                        f"silently and the dataset gets zero typed columns. "
                        f"Use the *-metadata-annot.csv / *-annot.csv file instead.")
                else:
                    with open(p, newline='', errors='replace') as f:
                        rows = list(csv.reader(f))[1:]
                    yes = sum(1 for r in rows if len(r) == 4 and r[2].strip() == 'Yes')
                    if yes == 0:
                        err(f"[{did}] annot {os.path.basename(p)}: 0 rows match "
                            f"`len(row)==4 and row[2]=='Yes'` — no columns will show")
                    else:
                        print(f"  [{did}] annot OK — {yes} columns exposed")

        for m in d.get('matrices', []):
            rel = m.get('path')
            if not m.get('name'):
                err(f"[{did}] a matrix has no `name` (used as the unit label "
                    f"and in the download filename)")
            if skip_paths or not rel or '<<<FILL' in str(rel) or '<<<FILL' in str(ddir):
                continue
            p = os.path.join(ddir, rel)
            if not os.path.exists(p):
                err(f"[{did}] matrix: not found -> {p}"); continue
            hdr = header_of(p)
            if len(hdr) < 3:
                err(f"[{did}] matrix {os.path.basename(p)} has {len(hdr)} columns "
                    f"— expected genes x samples (wide)")
            with open(p, newline='', errors='replace') as f:
                r = csv.reader(f); next(r); row2 = next(r, None)
            if row2 and not row2[0].strip().strip('"').upper().startswith('ENSG'):
                err(f"[{did}] matrix {os.path.basename(p)}: first column of row 2 "
                    f"is {row2[0][:30]!r}, expected an Ensembl gene ID. main.py "
                    f"annotates on ENSG and drops every row that fails.")

        # customFilter column must exist
        cf = d.get('customFilter')
        if cf and did in meta_headers:
            col = cf.get('column')
            if col and col not in meta_headers[did]:
                err(f"[{did}] customFilter.column {col!r} is not a column in the "
                    f"metadata CSV — z-score region subsets will be empty. "
                    f"Available: {meta_headers[did][:8]}...")

    # ---- category orders --------------------------------------------------
    for o in cfg.get('customMetadataCategoryOrders', []):
        var, order = o.get('variable'), o.get('order', [])
        grp = o.get('groups', [])
        if grp:
            tot = sum(g.get('size', 0) for g in grp)
            if tot != len(order):
                err(f"customMetadataCategoryOrders[{var!r}]: group sizes sum to "
                    f"{tot} but `order` has {len(order)} entries — they must match")
        for did in o.get('datasets', []):
            if did not in ids:
                warn(f"customMetadataCategoryOrders[{var!r}] lists unknown dataset {did!r}")
            elif did in meta_headers and var not in meta_headers[did]:
                near = [c for c in meta_headers[did]
                        if c.replace(' ', '').lower() == str(var).replace(' ', '').lower()]
                err(f"[{did}] category order variable {var!r} matches no column. "
                    f"main.py:429 compares it to the header with `==`, so the "
                    f"ordering silently never applies."
                    + (f" Did you mean {near[0]!r}?" if near else ""))
        # values outside the declared order get no position
        for did in o.get('datasets', []):
            if did in meta_headers and var in meta_headers[did]:
                d = next(x for x in datasets if x.get('id') == did)
                p = os.path.join(d.get('dir', ''), d.get('meta', ''))
                if skip_paths or not os.path.exists(p):
                    continue
                i = meta_headers[did].index(var)
                with open(p, newline='', errors='replace') as f:
                    r = csv.reader(f); next(r)
                    vals = {row[i].strip() for row in r if len(row) > i and row[i].strip()}
                missing = sorted(vals - set(order))
                if missing:
                    warn(f"[{did}] {var!r} values absent from `order`, they will "
                         f"lose their position: {missing}")

    # ---- groups -----------------------------------------------------------
    KNOWN_GROUPS = {'Bulk', 'SingleCell'}   # hardcoded in geneview.svelte:15-16
    seen_group_ids = set()
    for g in cfg.get('groups', []) or []:
        gid = g.get('id')
        if gid is not None:
            seen_group_ids.add(gid)
            if gid not in KNOWN_GROUPS:
                err(f"groups id {gid!r} is not one the frontend looks up. "
                    f"geneview.svelte:15-16 asks for 'Bulk' and 'SingleCell' by "
                    f"literal string; the live bundle's groups/.attrs['order'] is "
                    f"['Bulk','SingleCell']. Any other id creates an HDF5 group "
                    f"nothing reads, and the corresponding tab stays greyed out. "
                    f"(Panel TITLES live in the frontend, not this file.)")
        if 'id' not in g:
            err(f"a groups entry has no `id` (main.py:836 reads pg['id']). "
                f"Got keys: {list(g.keys())}")
        for did in g.get('datasets', []):
            if did not in ids:
                err(f"groups[{g.get('id')!r}] lists unknown dataset {did!r} — "
                    f"main.py swallows this with contextlib.suppress(KeyError), "
                    f"so the dataset silently vanishes from that panel")
    for missing in sorted(KNOWN_GROUPS - seen_group_ids):
        warn(f"no group with id {missing!r} — the corresponding tab "
             f"({'Gene Exp Across Variables (Bulk)' if missing=='Bulk' else 'Cell Type Expression'}) "
             f"will be greyed out for every gene")

    grouped = {x for g in (cfg.get('groups') or []) for x in g.get('datasets', [])}
    for i in ids:
        if i and i not in grouped:
            warn(f"dataset {i!r} is in no group — it will not appear in either panel")

    # ---- MIN_HITS ---------------------------------------------------------
    if len(datasets) < 2:
        err(f"only {len(datasets)} dataset(s). main.py has MIN_HITS = 2 and drops "
            f"any gene not present in >=2 datasets, so this run writes ZERO genes. "
            f"Set MIN_HITS = 1 for a single-dataset smoke test.")

    # ---- deploy -----------------------------------------------------------
    if cfg.get('deploy_local') is False:
        warn("deploy_local is False — this run UPLOADS TO PRODUCTION. The bucket "
             "is hardcoded at main.py:45/49 (deploy_bucket is not read) and there "
             "is no S3 versioning, so there is no rollback.")

    # ---- report -----------------------------------------------------------
    print()
    for w in WARNINGS: print(f"WARN   {w}")
    for e in ERRORS:   print(f"ERROR  {e}")
    print(f"\n{len(ERRORS)} error(s), {len(WARNINGS)} warning(s)")
    if not ERRORS:
        print("OK — no blocking problems found." if not n_fill else
              "No blocking problems in the structure. Fill the placeholders, "
              "then re-run without --skip-paths to check the files.")
    return 1 if ERRORS else 0


if __name__ == '__main__':
    sys.exit(main())

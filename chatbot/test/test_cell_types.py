"""
Single-nucleus cell-type queries, unit labelling, and dataset declaration.

    BITHUB_REMOTE_DATA=1 .venv/bin/python test_cell_types.py

Covers three bugs found by exercising all eight datasets rather than
BrainSpan alone — each was unreachable while only one dataset loaded:

1. get_expression raised KeyError: 'Period' on Cameron, HCA and Velmeshev.
   The single-nucleus sets have no developmental period (they are cell-type
   resolved, not time-resolved) but the method grouped by "Period"
   unconditionally, so three of eight datasets crashed on the most basic
   query. It now picks the finest available stratum, or returns region means
   only when there is no developmental axis at all.

2. Every payload was labelled log2(RPKM+1) and attributed to BrainSpan,
   because both strings were hardcoded rather than read from the loader.
   GTEx and PsychENCODE are TPM; the three single-nucleus sets are CPM. A
   TPM value reported as RPKM is a wrong number with a plausible unit, which
   is worse than an error.

3. Only 3 of 9 tools declared `dataset` in their schema, although
   dispatch_tool has always routed on args["dataset"] and the system prompt
   instructs the model to pass it. The model could not name a dataset, so it
   silently got selection[0].

Plus the tool added for the single-nucleus sets: get_cell_type_expression.
It is validated against canonical markers rather than a fixed expected
number — the level names are not stable across pipeline freezes (Cameron's
are 'OPC'/'Endothelial' in one and 'OPCs'/'Endothelia' in another), so
asserting on marker RANK is robust where asserting on labels or values is
not.
"""

import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-only-not-used")

import anthropic  # noqa: E402

anthropic.Anthropic = lambda *a, **k: type("C", (), {"messages": None})()

from agent import TOOLS, dispatch_tool, _PER_DATASET_TOOLS  # noqa: E402

# Datasets with per-nucleus cell-type labels, and bulk sets that must refuse.
SINGLE_NUCLEUS = ("Cameron", "HCA", "Velmeshev")
BULK = ("BrainSpan", "BrainSeq", "HDBR", "GTEx", "PsychENCODE")

# Native quantification unit per dataset — the point of bug 2.
EXPECTED_UNIT = {
    "BrainSpan": "log2(RPKM+1)", "BrainSeq": "log2(RPKM+1)",
    "HDBR": "log2(RPKM+1)", "GTEx": "log2(TPM+1)",
    "PsychENCODE": "log2(TPM+1)", "Cameron": "log2(CPM+1)",
    "HCA": "log2(CPM+1)", "Velmeshev": "log2(CPM+1)",
}

# Canonical markers -> the cell type that must rank first. Deliberately a
# substring, so 'Endothelia' and 'Endothelial' both pass.
#
# Split by dataset age, because the correct answer genuinely differs.
# Cameron is 13-15pcw: mature astrocytes and oligodendrocytes do not exist
# yet, and GFAP / AQP4 / PLP1 are expressed by RADIAL GLIA at that stage. A
# single marker table would either fail on Cameron or assert something
# developmentally wrong, so the adult sets and the fetal set get their own.
ADULT_MARKERS = {
    "GFAP": "Astrocyte", "AQP4": "Astrocyte",
    "CSF1R": "Microglia", "P2RY12": "Microglia",
    "PLP1": "Oligodendrocyte",
    "GAD1": "Inhibitory",
}

# Mid-gestation: progenitor markers, plus the glial markers reassigned to the
# progenitor that actually expresses them at this stage.
FETAL_MARKERS = {
    "SOX2": "progenitor",          # cycling progenitor
    "EOMES": "Intermediate",       # intermediate progenitor
    "OLIG1": "OPC",
    "P2RY12": "Microglia",
    "GAD1": "Inhibitory",
    "VIM": "Radial glia",
    "GFAP": "Radial glia",         # NOT astrocytes at 13-15pcw
    "AQP4": "Radial glia",
    "SLC17A7": "Excitatory",
}

MARKERS_BY_DATASET = {
    "HCA": ADULT_MARKERS,
    "Velmeshev": ADULT_MARKERS,
    "Cameron": FETAL_MARKERS,
}


def main() -> int:
    import main as app  # noqa: PLC0415 - after the stub is installed

    registry = app.registry
    loaded = registry.available
    print(f"datasets loaded    {len(loaded)}: {', '.join(loaded)}")

    # Selection is one dataset throughout: routing must come from the
    # `dataset` argument, not from what happens to be selected.
    selection = [loaded[0]]

    def call(tool, **args):
        return json.loads(dispatch_tool(tool, args, registry, selection))

    # ── 1. every per-gene tool declares `dataset` ─────────────────────────
    # Derived from the dispatcher's own set rather than restated here: a
    # hardcoded copy silently stops covering tools added later, which is
    # exactly what happened to the six added after this test was written.
    must_declare = set(_PER_DATASET_TOOLS)
    for name in sorted(must_declare):
        schema = next((t for t in TOOLS if t["name"] == name), None)
        assert schema is not None, f"no such tool: {name}"
        assert "dataset" in schema["input_schema"]["properties"], (
            f"{name} has no `dataset` parameter — dispatch routes on it but "
            "the model cannot pass it."
        )
    # compare_datasets takes a `datasets` LIST; declaring the singular form
    # would invite a call the dispatcher cannot honour.
    cmp_schema = next(t for t in TOOLS if t["name"] == "compare_datasets")
    assert "dataset" not in cmp_schema["input_schema"]["properties"], (
        "compare_datasets must not declare the singular `dataset`"
    )
    print(f"schema ok          {len(must_declare)} tools accept `dataset`; "
          "compare_datasets correctly does not")

    # ── 2. get_expression works on all eight, with the right unit ─────────
    for name in loaded:
        out = call("get_expression", gene="SHANK3", dataset=name)
        assert "error" not in out, f"{name}: {out['error']}"
        assert out["dataset"] == name, (
            f"requested {name}, payload says {out['dataset']} — the "
            "hardcoded attribution is back."
        )
        assert out["unit"] == EXPECTED_UNIT[name], (
            f"{name}: unit is {out['unit']}, expected "
            f"{EXPECTED_UNIT[name]} — a TPM/CPM value labelled RPKM."
        )
        assert out["note"].count(name) >= 1, f"{name}: note names another dataset"
        assert out["n_samples"] > 0, f"{name}: no samples"
        # The table must not be a grid of empty cells: every declared column
        # has to be populated in at least one row.
        keys = [c["key"] for c in out["table"]["columns"]]
        for i, key in enumerate(keys):
            assert any(r[i] is not None for r in out["table"]["rows"]), (
                f"{name}: table column {key!r} is entirely empty"
            )
    print(f"get_expression ok  all {len(loaded)} datasets, correct units "
          "(no KeyError: 'Period')")

    # Single-nucleus sets have no Period; that must be visible, not silent.
    for name in SINGLE_NUCLEUS:
        out = call("get_expression", gene="SHANK3", dataset=name)
        assert out["grouped_by"] != "Period", (
            f"{name} reports grouping by Period, which it does not have"
        )
    for name in BULK:
        out = call("get_expression", gene="SHANK3", dataset=name)
        assert out["grouped_by"] == "Period", (
            f"{name} is bulk and should stratify by Period, got "
            f"{out['grouped_by']}"
        )
    print("stratum ok         bulk uses Period; single-nucleus falls back")

    # ── 3. cell-type tool: markers must rank first ────────────────────────
    for name in SINGLE_NUCLEUS:
        levels = registry.get(name).cell_type_levels()
        assert "MajorCellType" in levels, (
            f"{name} has no MajorCellType column — it is the only cell-type "
            "grouping all three single-nucleus sets share."
        )
        checked = 0
        for gene, expect in MARKERS_BY_DATASET[name].items():
            out = call("get_cell_type_expression", gene=gene, dataset=name)
            if "error" in out:
                continue        # gene absent from this dataset's matrix
            assert out["dataset"] == name
            assert out["unit"] == EXPECTED_UNIT[name]
            top = out["highest"]["cell_type"]
            if not any(expect.lower() in lv.lower() for lv in levels["MajorCellType"]):
                continue        # that cell type is not annotated here
            assert expect.lower() in top.lower(), (
                f"{name}: {gene} should be highest in a {expect} population, "
                f"got {top!r} — cell-type grouping is wrong."
            )
            # Enrichment must be positive for a marker of its own cell type.
            assert out["highest"]["vs_dataset_mean"] > 0, (
                f"{name}: {gene} top cell type is not above the dataset mean"
            )
            checked += 1
        assert checked >= 3, f"{name}: only {checked} markers checked"
        print(f"markers ok         {name}: {checked} canonical markers rank "
              f"in the right cell type ({len(levels['MajorCellType'])} types)")

    # ── 4. requested cell_type, fuzzy matching, and highlighting ──────────
    out = call("get_cell_type_expression", gene="P2RY12", dataset="Velmeshev",
               cell_type="microglia")           # lower case on purpose
    req = out["requested_cell_type"]
    assert req and "microglia" in req["cell_type"].lower(), (
        f"case-insensitive match failed: {req}"
    )
    assert out["table"]["highlight_row"] == out["by_cell_type"].index(req), (
        "highlight_row does not point at the requested cell type"
    )
    print(f"request ok         'microglia' -> {req['cell_type']} "
          f"(n={req['n']}, highlighted row {out['table']['highlight_row']})")

    # A bad level name must list the real ones rather than return nothing.
    out = call("get_cell_type_expression", gene="SHANK3", dataset="HCA",
               cell_type="Purkinje cells")
    assert "error" in out and "Purkinje" in out["error"], out
    assert "Astrocytes" in out["error"], (
        "rejection does not list the available cell types"
    )
    print("bad level ok       refused, and named the available cell types")

    # ── 5. finer resolutions, where present ───────────────────────────────
    # The finer column is DISCOVERED, not named: HCA carried a 'Class' column
    # (GABAergic / Glutamatergic) in the Aug 16 freeze and does not in the
    # Aug 31 one, where 'Subclass' carries that resolution. Hardcoding the
    # name is what broke this assertion, and it is the same drift
    # cell_type_levels() exists to absorb.
    finer = [c for c in registry.get("HCA").cell_type_levels()
             if c not in ("MajorCellType", "CorticalLayer")]
    assert finer, "HCA should expose at least one finer cell-type grouping"
    resolution = finer[0]

    out = call("get_cell_type_expression", gene="GAD1", dataset="HCA",
               resolution=resolution)
    assert out["resolution"] == resolution, out
    by = {r["cell_type"]: r["mean"] for r in out["by_cell_type"]}

    # Biology, asserted without naming a level: GAD1 is the GABA-synthesising
    # enzyme, so whichever level tops this ranking must be an inhibitory /
    # GABAergic one and must beat every excitatory / glutamatergic level.
    top = max(by, key=by.get)
    inhibitory = [c for c in by if any(
        k in c.lower() for k in ("gaba", "inhibitory", "in-", "pvalb",
                                 "sst", "vip", "lamp5", "sncg", "chandelier"))]
    excitatory = [c for c in by if any(
        k in c.lower() for k in ("glutamat", "excitatory", "exc", " it", "l4 it",
                                 "l5 et", "l6 ct", "l6b", "np"))]
    assert inhibitory, f"no inhibitory level recognised among {sorted(by)}"
    assert top in inhibitory, (
        f"GAD1 should peak in an inhibitory level, peaked in '{top}': {by}"
    )
    if excitatory:
        assert max(by[c] for c in inhibitory) > max(by[c] for c in excitatory), (
            f"GAD1 must exceed every excitatory level: {by}"
        )
    print(f"resolution ok      HCA {resolution}: GAD1 peaks in '{top}' "
          f"({by[top]:.2f}), above every excitatory level")

    out = call("get_cell_type_expression", gene="SHANK3", dataset="Cameron",
               resolution="NotAColumn")
    assert "error" in out and "NotAColumn" in out["error"], out
    print("bad resolution ok  refused, and named the available groupings")

    # ── 6. bulk datasets refuse, and say what to use instead ──────────────
    for name in BULK:
        out = call("get_cell_type_expression", gene="SHANK3", dataset=name)
        assert "error" in out, (
            f"{name} is bulk tissue and must not return cell-type means — "
            "each sample is a mixture."
        )
        assert "get_variance_partition" in out["error"], (
            f"{name}: refusal does not point at the tool that does answer "
            "cell-type questions for bulk data"
        )
    print(f"bulk refusal ok    {len(BULK)} bulk datasets refused with guidance")

    print("\nAll cell-type, unit and dataset-declaration checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

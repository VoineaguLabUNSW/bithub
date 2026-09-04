#!/usr/bin/env python3
"""
Checks for the tools added after the data-depth survey.

Run:  ANTHROPIC_API_KEY=placeholder .venv/bin/python test_new_tools.py

These are the six statistical / annotation tools plus the composition figure.
The assertions are deliberately about the STATISTICS and the REFUSALS rather
than exact numbers: the published bundle is re-cut periodically (the Aug 31
2026 freeze renamed HCA's 'Class' column to 'Subclass' and broke a hardcoded
assertion in test_cell_types.py), so anything pinned to a level name or a
p-value to three decimals is a future false alarm.

What is worth pinning, and is pinned here:

  * Pseudoreplication is actually handled. Velmeshev has 81,215 nuclei from
    31 donors; a nucleus-level t-test on that reports p~1e-3 for SHANK3 in
    ASD, and the donor-level test reports p~0.36. If a change ever makes the
    tool report the former, that is a wrong answer with a plausible number
    attached, which is the worst failure mode this chat has. Asserted as
    "aggregated_to_donor is True and n_donors is small", not as a p-value.

  * Every refusal names its reason. A tool that returns an empty result for
    HDBR (all controls) or HCA (no Diagnosis column) invites the model to
    invent an explanation; a tool that raises with the reason in the string
    gets it repeated back correctly.

  * statistical_note.text is non-empty wherever the tool can mislead, because
    the system prompt tells the model to lift that string verbatim.
"""
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
os.environ.setdefault("ANTHROPIC_API_KEY", "placeholder")

import main as app                                          # noqa: E402
from agent import TOOLS, dispatch_tool, _PER_DATASET_TOOLS  # noqa: E402

BULK = ("BrainSpan", "BrainSeq", "HDBR", "GTEx", "PsychENCODE")
SINGLE_NUCLEUS = ("Cameron", "HCA", "Velmeshev")

NEW_TOOLS = (
    "compare_by_diagnosis", "compare_cell_type_by_diagnosis",
    "correlate_with_covariate", "correlate_genes",
    "get_cell_type_composition", "find_genes_in_locus", "gene_info",
)


def main() -> int:
    registry = app.registry
    selection = list(registry.available)

    def call(tool, **args):
        return json.loads(dispatch_tool(tool, args, registry, selection))

    # ── 1. all new tools are registered, routed and dataset-scoped ─────────
    names = {t["name"] for t in TOOLS}
    for tool in NEW_TOOLS:
        assert tool in names, f"{tool} is not in TOOLS"
        assert tool in _PER_DATASET_TOOLS, f"{tool} is not dataset-scoped"
        schema = next(t for t in TOOLS if t["name"] == tool)
        assert "dataset" in schema["input_schema"]["properties"], tool
        # An unknown tool name falls through dispatch_tool to "Unknown tool";
        # reaching a real branch is what we are checking.
        out = call(tool, gene="SHANK3", other_gene="SHANK2", chromosome="22",
                   start=50_600_000, end=50_800_000, dataset="BrainSpan")
        assert "Unknown tool" not in str(out.get("error", "")), tool
    print(f"registered ok      {len(NEW_TOOLS)} tools routed and dataset-scoped")

    # ── 2. pseudoreplication: the trap this suite exists for ───────────────
    out = call("compare_by_diagnosis", gene="SHANK3", dataset="Velmeshev")
    note = out["statistical_note"]
    assert note["aggregated_to_donor"] is True, (
        "Velmeshev must be aggregated to donor level before testing; "
        f"got {note}"
    )
    assert note["unit_of_analysis"] == "donor", note
    assert note["n_donors"] < 100, (
        f"donor count should be tens, not nuclei: {note['n_donors']}"
    )
    assert note["n_observations"] > 10_000, note
    assert note["text"].strip(), "aggregation must be stated in prose"
    asd = next(c for c in out["comparisons"] if "ASD" in c["diagnosis"])
    assert asd["p"] > 0.01, (
        "a donor-level SHANK3 ASD test should NOT be significant; "
        f"p={asd['p']:.2e} suggests the nucleus-level test leaked through"
    )
    print(f"donor-level ok     Velmeshev: {note['n_observations']:,} nuclei -> "
          f"{note['n_donors']} donors, ASD p={asd['p']:.2f} (not 1e-3)")

    # Bulk datasets with one sample per donor need no aggregation.
    out = call("compare_by_diagnosis", gene="SHANK3", dataset="PsychENCODE")
    assert out["statistical_note"]["unit_of_analysis"] == "sample", out
    small = [w for w in out["statistical_note"]["warnings"] if "Small group" in w]
    assert small, "Affective Disorder (n=8) should trigger a small-group warning"
    print(f"small group ok     PsychENCODE flagged: {small[0][:58]}…")

    # ── 3. refusals name their reason ──────────────────────────────────────
    # HDBR carried a Diagnosis column (all controls) in the Aug 16 freeze and
    # does not in the Aug 31 one, so it may take either the no-column or the
    # single-level branch. Both must refuse and both must name the datasets
    # that do support the comparison — that is what the assertion pins.
    for name in ("HDBR", "BrainSpan"):
        out = call("compare_by_diagnosis", gene="SHANK3", dataset=name)
        assert "error" in out, f"{name} must refuse: {out}"
        assert "Diagnosis" in out["error"] or "Control" in out["error"], out
        assert "PsychENCODE" in out["error"], (
            f"{name} refusal must name a dataset that works: {out['error']}"
        )
    out = call("compare_cell_type_by_diagnosis", gene="SHANK3",
               dataset="PsychENCODE")
    assert "error" in out and "cell-type" in out["error"], out
    out = call("get_cell_type_composition", dataset="HCA")
    assert "error" in out and "MultiBrain" in out["error"], out
    print("refusals ok        HDBR, BrainSpan, PsychENCODE, HCA each explained")

    # ── 4. cell-type x diagnosis ───────────────────────────────────────────
    out = call("compare_cell_type_by_diagnosis", gene="SHANK3",
               dataset="Velmeshev")
    assert out["largest_difference"]["cell_type"] in {
        r["cell_type"] for r in out["by_cell_type"]
    }, out
    assert "multiple" in out["statistical_note"]["text"].lower(), (
        "untested multiplicity must be disclosed: "
        f"{out['statistical_note']['text']}"
    )
    print(f"celltype x dx ok   largest: "
          f"{out['largest_difference']['cell_type']}, multiplicity disclosed")

    # ── 5. covariates: direction and ranking ───────────────────────────────
    out = call("correlate_with_covariate", gene="SHANK3", dataset="GTEx")
    assert out["n_covariates_tested"] > 5, out
    rhos = [abs(c["rho"]) for c in out["correlations"]]
    assert rhos == sorted(rhos, reverse=True), "must be ranked by |rho|"
    rin = next((c for c in out["correlations"] if c["covariate"] == "RIN"), None)
    assert rin is not None and rin["rho"] > 0, (
        f"GTEx SHANK3 should track RIN positively: {rin}"
    )
    out = call("correlate_with_covariate", gene="SHANK3", dataset="GTEx",
               covariate="NotAColumn")
    assert "error" in out and "NotAColumn" in out["error"], out
    print(f"covariates ok      GTEx: {len(rhos)} ranked, RIN rho={rin['rho']:+.3f}")

    # ── 6. gene-gene correlation ───────────────────────────────────────────
    out = call("correlate_genes", gene="SHANK3", other_gene="SHANK2",
               dataset="BrainSpan")
    assert out["direction"] in ("positive", "negative"), out
    assert -1 <= out["spearman_rho"] <= 1, out
    same = call("correlate_genes", gene="SHANK3", other_gene="SHANK3",
                dataset="BrainSpan")
    assert "error" in same, "correlating a gene with itself must be refused"
    print(f"gene-gene ok       SHANK3/SHANK2 rho={out['spearman_rho']:+.3f}, "
          "self-correlation refused")

    # ── 7. composition sums to one and lands where the UI reads it ─────────
    for name in BULK:
        out = call("get_cell_type_composition", dataset=name)
        total = sum(out["composition"].values())
        assert abs(total - 1) < 0.02, f"{name} proportions sum to {total}"
        # The agent loop collects renderables from "table" only; a bar under
        # any other key is silently dropped from the UI.
        assert out["table"]["type"] == "stacked_bar", out["table"]["type"]
        assert out["statistical_note"]["text"].strip(), name
    grouped = call("get_cell_type_composition", dataset="BrainSpan",
                   group_by="AgeInterval")
    assert len(grouped["by_stratum"]) > 5, grouped
    assert grouped["grouped_by"] == "AgeInterval"
    print(f"composition ok     5 bulk sets sum to 1.0; BrainSpan splits into "
          f"{len(grouped['by_stratum'])} age intervals")

    # ── 8. composition figures, and the pie's honest refusal ───────────────
    fig = call("generate_figure", figure_type="composition", dataset="BrainSpan")
    assert fig["plotly_layout"]["barmode"] == "stack", fig["plotly_layout"]
    assert len(fig["plotly_data"]) >= 4, fig
    pie = call("generate_figure", figure_type="composition_pie",
               dataset="BrainSpan")
    assert pie["plotly_data"][0]["type"] == "pie", pie
    refused = call("generate_figure", figure_type="composition_pie",
                   dataset="BrainSpan", group_by="AgeInterval")
    assert "error" in refused and "compared by eye" in refused["error"], (
        "a pie split across strata must be refused, not drawn: " + str(refused)
    )
    print("figures ok         stacked bar drawn; split pie refused with reason")

    # ── 9. annotation tools ────────────────────────────────────────────────
    out = call("find_genes_in_locus", chromosome="22", start=50_000_000,
               end=51_300_000, dataset="BrainSpan")
    symbols = {g["gene"] for g in out["genes"]}
    assert "SHANK3" in symbols, sorted(symbols)[:10]
    starts = [g["start"] for g in out["genes"]]
    assert starts == sorted(starts), "genes must come back position-ordered"
    # 'chr22' and '22' must resolve identically.
    assert call("find_genes_in_locus", chromosome="chr22", start=50_000_000,
                end=51_300_000, dataset="BrainSpan")["n_genes"] == out["n_genes"]
    assert "error" in call("find_genes_in_locus", chromosome="99", start=1,
                           end=2, dataset="BrainSpan")

    info = call("gene_info", gene="SHANK3", dataset="BrainSpan")
    assert info["chr"] == "22" and info["start"] > 0, info
    assert len(info["in_datasets"]) == 8, info

    # The presence index must DISCRIMINATE, not report everything everywhere.
    loader = registry.get("BrainSpan")
    absent_somewhere = [
        s for s, idx in zip(loader.annotation["symbol"],
                            loader.gene_presence["HCA"]) if int(idx) < 0
    ]
    assert 1000 < len(absent_somewhere) < len(loader.annotation), (
        f"HCA should carry fewer genes than the annotation: "
        f"{len(absent_somewhere)} absent"
    )
    partial = call("gene_info", gene=absent_somewhere[0], dataset="BrainSpan")
    assert partial["absent_from"], partial
    assert "HCA" in partial["absent_from"], partial
    assert "error" in call("gene_info", gene="NOTAGENE", dataset="BrainSpan")
    print(f"annotation ok      chr22 locus -> {out['n_genes']} genes ordered; "
          f"{len(absent_somewhere):,} genes absent from HCA")

    # ── 10. CorticalLayer is offered where it exists, refused where not ────
    layers = registry.get("HCA").cell_type_levels()
    assert "CorticalLayer" in layers, layers
    assert list(layers)[0] == "MajorCellType", (
        "MajorCellType must stay the default grouping"
    )
    out = call("get_cell_type_expression", gene="SLC17A7",
               resolution="CorticalLayer", dataset="HCA")
    assert out["resolution"] == "CorticalLayer", out
    assert len(out["by_cell_type"]) > 5, out
    refused = call("get_cell_type_expression", gene="SLC17A7",
                   resolution="CorticalLayer", dataset="Velmeshev")
    assert "error" in refused and "CorticalLayer" in refused["error"], refused
    print(f"layers ok          HCA: {len(out['by_cell_type'])} cortical layers; "
          "Velmeshev refused")

    print("\nAll new-tool checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""
Loader smoke test — no API key needed, no credits spent.

    .venv/bin/python test_agent.py            # loader only
    .venv/bin/python test_agent.py --agent    # also does one live model call

Checks the data layer against the real files and asserts the invariants the
agent depends on: that superlatives are computed rather than inferred, and
that variance components sum to 1.

Covers the LOCAL CSV/parquet path only. This deployment reads the site's
published bundle instead, so chatbot/data/ is absent and this suite SKIPS.
The bundle path is covered by test_remote_loader.py, test_metadata_scope.py,
test_cell_types.py, test_new_tools.py and test_doc_figures.py.
"""

import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))      # runnable from any cwd
DATA = HERE / "data"


def main() -> int:
    from data_loader import BrainSpanLoader

    # This suite exercises the LOCAL CSV/parquet loader, which is not how this
    # deployment reads data — it reads the site's published bundle, and
    # chatbot/data/ is deliberately absent here. Skip rather than fail: a red
    # suite for a path nobody uses trains people to ignore red suites. The
    # bundle path is covered by test_remote_loader / test_metadata_scope /
    # test_cell_types / test_new_tools / test_doc_figures.
    if not (DATA / "BrainSpan-exp.csv").exists():
        print("SKIP: chatbot/data/ not present — this suite covers the local")
        print("      CSV loader. This deployment reads the published bundle;")
        print("      run the bundle suites instead (see docstring above).")
        return 0

    loader = BrainSpanLoader(
        expr_path=DATA / "BrainSpan-exp.csv",
        meta_path=DATA / "BrainSpan-metadata.csv",
        vp_path=DATA / "BrainSpan_varPart.csv",
        vp_decon_path=DATA / "BrainSpan_varPart_cellTypes.csv",
        annotation_path=DATA / "gene_annotation.csv",
    )

    expr = loader.get_expression("SHANK3")
    assert expr["n_samples"] > 0
    print(f"\nexpression        {expr['gene']} n={expr['n_samples']} {expr['unit']}")
    for region, periods in sorted(expr["expression_by_region_and_period"].items()):
        print(f"  {region:<12}" + "  ".join(f"{p} {v:.2f}" for p, v in sorted(periods.items())))

    traj = loader.get_developmental_trajectory("SHANK3")
    steep = traj["steepest_transition"]
    deltas = [abs(t["delta"]) for t in traj["transitions_by_magnitude"]]
    assert abs(steep["delta"]) == max(deltas), "steepest_transition is not the largest delta"
    print(f"\ntrajectory        {len(traj['trajectory'])} age intervals")
    print(f"  steepest        {steep['from']} -> {steep['to']}  {steep['delta']:+.3f}")

    vp = loader.get_variance_partition("SHANK3")
    total = sum(vp["variance_components"].values())
    assert abs(total - 1.0) < 0.01, f"variance components sum to {total}, expected 1"
    print(f"\nvariance          top {vp['top_component']['component']} "
          f"{vp['top_component']['fraction']:.1%} · technical {vp['technical_total']:.1%} "
          f"· residual {vp['residual']:.1%}")

    peak = traj["peak"]
    assert peak["mean"] == max(p["mean"] for p in traj["trajectory"]), "peak is not the maximum"
    print(f"  peak            {peak['age_interval']} {peak['mean']:.2f} (n={peak['n']})")

    tbl = traj["table"]
    assert len(tbl["rows"]) == len(traj["trajectory"])
    assert tbl["rows"][tbl["highlight_row"]][0] == peak["age_interval"], \
        "highlighted row is not the peak"
    print(f"  table           {len(tbl['rows'])} rows, peak highlighted at index {tbl['highlight_row']}")

    meta = loader.describe_metadata()
    assert meta["variables"]["PMI"]["n_missing"] > 0, "PMI missingness should be reported"
    print(f"\nmetadata          {len(meta['variables'])} variables, "
          f"{len(meta['incomplete_variables'])} incomplete")
    pmi = loader.describe_metadata("PMI (hours)")["variables"]["PMI"]
    print(f"  PMI             {pmi['min']}–{pmi['max']} h (median {pmi['median']}), "
          f"{pmi['n_present']}/{meta['n_samples']} samples")

    for payload in (expr, traj, vp, meta):
        assert "table" in payload, "every tabular tool should return a table"
    assert expr["unit"] == "log2(RPKM+1)", f"unit is {expr['unit']}, expected RPKM"

    import json
    for kind, fn in (("expression", loader.get_expression_figure),
                     ("trajectory", loader.get_trajectory_figure),
                     ("variance",   loader.get_variance_figure)):
        json.dumps(fn("SHANK3"))          # must be JSON-serialisable for the API
        print(f"figure ok         {kind}")

    sc = loader.get_scatter_figure("SHANK3", x="AgeNumeric",
                                   color_by="Regions", symbol_by="Period")
    json.dumps(sc)
    n_pts = sum(len(t["x"]) for t in sc["plotly_data"])
    assert n_pts == expr["n_samples"], f"scatter dropped points: {n_pts}"
    print(f"figure ok         scatter ({len(sc['plotly_data'])} traces, {n_pts} points)")

    hm = loader.get_heatmap_figure(["SHANK3", "MECP2", "FOXP2"], group_by="AgeInterval")
    json.dumps(hm)
    assert len(hm["plotly_data"][0]["z"]) == 3
    print(f"figure ok         heatmap ({len(hm['genes'])} genes x "
          f"{len(hm['plotly_data'][0]['x'])} groups)")

    # Variance renders as a proportion bar, not a table. Segments must sum to 1
    # and every component must be accounted for — a bar that silently drops a
    # component would understate what is unexplained.
    vp = loader.get_variance_partition("SHANK3")
    bar = vp["table"]
    assert bar["type"] == "stacked_bar", f"variance returned {bar['type']}"
    assert abs(bar["total"] - 1.0) < 0.001, f"segments sum to {bar['total']}"
    assert all(seg.get("color") for seg in bar["segments"]), "segment without a colour"
    assert bar["segments"][-1]["label"] == "Residuals", "Residuals must close the bar"

    # Nothing may vanish: merged slivers are listed under the Other segment.
    shown = {seg["label"] for seg in bar["segments"]}
    merged = {c["label"] for seg in bar["segments"]
              for c in seg.get("components", [])}
    missing = set(vp["variance_components"]) - shown - merged
    assert not missing, f"components absent from the bar and from Other: {missing}"
    print(f"figure ok         variance bar ({len(bar['segments'])} segments, "
          f"top {bar['segments'][0]['label']} {bar['segments'][0]['percent']}%)")

    # Box distributions must agree with the trajectory means they sit beside —
    # two figures disagreeing about the same gene is the failure mode that
    # makes a grounded assistant untrustworthy.
    bx = loader.get_box_figure("SHANK3", group_by="AgeInterval")
    json.dumps(bx)
    assert all(t["type"] == "box" for t in bx["plotly_data"])
    traj_means = {p["age_interval"]: p["mean"]
                  for p in loader.get_developmental_trajectory("SHANK3")["trajectory"]}
    for trace in bx["plotly_data"]:
        expected = traj_means.get(trace["name"])
        if expected is None:
            continue
        actual = sum(trace["y"]) / len(trace["y"])
        assert abs(actual - expected) < 0.001, (
            f"box mean for {trace['name']} is {actual:.3f} but the trajectory "
            f"reports {expected:.3f} — the two figures disagree."
        )
    print(f"figure ok         box ({len(bx['plotly_data'])} groups, means match trajectory)")

    bxs = loader.get_box_figure("SHANK3", group_by="Regions", split_by="Period")
    json.dumps(bxs)
    assert len(bxs["plotly_data"]) == 2, "split_by should give one trace per level"
    print(f"figure ok         box split ({[t['name'] for t in bxs['plotly_data']]})")

    for label, call in (
        ("categorical x",   lambda: loader.get_scatter_figure("SHANK3", x="Regions")),
        ("too many levels", lambda: loader.get_scatter_figure(
            "SHANK3", color_by="StructureAcronym")),
        ("empty heatmap",   lambda: loader.get_heatmap_figure(["NOPE1", "NOPE2"])),
    ):
        try:
            call()
        except ValueError:
            print(f"rejected ok       {label}")
        else:
            raise AssertionError(f"{label} should raise ValueError")

    # The z-score scale must match pipeline/main.py exactly, or the chat and
    # the gene view disagree about the same gene. Guard both the constant and
    # a reference value.
    import re as _re
    from data_loader import PIPELINE_LOG2_OFFSET
    pipeline_src = (HERE.parent / "pipeline" / "main.py")
    if pipeline_src.exists():
        declared = float(_re.search(r"^LOG2_OFFSET\s*=\s*([\d.]+)",
                                    pipeline_src.read_text(), _re.M).group(1))
        assert declared == PIPELINE_LOG2_OFFSET, (
            f"pipeline/main.py uses LOG2_OFFSET={declared} but data_loader "
            f"uses {PIPELINE_LOG2_OFFSET}; z-scores will not match the site."
        )
        print(f"\nz-score scale     LOG2_OFFSET={declared} matches pipeline/main.py")

    # Pins the local computation. NOTE this is NOT the published value: the
    # live bundle reports ACTB at +3.109 because the pipeline standardises
    # over the 30,687 genes it writes, while this matrix has 52,376 rows.
    # Same transform, different reference population. Verified against
    # CloudFront: restricting to the bundle's gene set reproduces the
    # published z-scores to within 0.02 for 99.7% of genes (r = 0.9984).
    actb = loader.gene_zscore.loc[loader._resolve_gene("ACTB")]
    assert abs(actb - 3.595) < 0.01, (
        f"ACTB z-score is {actb:.3f}, expected ~3.595 for the 52,376-gene "
        "population — the log offset or the standardisation axis has drifted."
    )
    print(f"  ACTB            z={actb:+.3f} local (published bundle: +3.109 — "
          "different gene population, not a bug)")

    from data_loader import DatasetRegistry
    one = DatasetRegistry({"BrainSpan": loader})
    solo = one.compare_expression("SHANK3", ["BrainSpan", "GTEx"])
    assert solo["comparison_possible"] is False, "one dataset is not a comparison"
    assert any(u["dataset"] == "GTEx" for u in solo["unavailable"]), \
        "unloaded dataset must be reported, not dropped"
    assert "warning" in solo
    print(f"\ncross-dataset     1 loaded of 8; GTEx reported unavailable")
    print(f"  z-score         SHANK3 {solo['results'][0]['zscore']:+.3f} "
          f"(mean log2 {solo['results'][0]['mean_log2']:.2f} "
          f"{solo['results'][0]['native_unit']})")

    # Two datasets must produce a real comparison. Aliasing the same loader is
    # enough to exercise the code path until a second dataset is wired up.
    two = DatasetRegistry({"BrainSpan": loader, "BrainSeq": loader})
    pair = two.compare_expression("SHANK3")
    assert pair["comparison_possible"] is True and len(pair["results"]) == 2
    assert len(pair["table"]["rows"]) == 2
    print(f"  two datasets    comparison_possible=True, {len(pair['results'])} rows")

    try:
        loader.get_expression("NOTAREALGENE")
    except ValueError as exc:
        print(f"\nunknown gene      handled: {str(exc)[:60]}")
    else:
        raise AssertionError("unknown gene should raise ValueError")

    if "--agent" in sys.argv:
        from agent import run_agent          # imports fail fast without a key
        print("\n--- live agent call ---")
        result = run_agent("How does SHANK3 change across development?", loader)
        print("tools:", result["tools_used"])
        print(result["text"][:600])

    print("\nAll loader checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
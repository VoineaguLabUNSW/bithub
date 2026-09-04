"""
Per-dataset metadata profiling, and literature-search wiring.

    BITHUB_REMOTE_DATA=1 .venv/bin/python test_metadata_scope.py

Covers two bugs found by asking the running chatbot real questions:

1. describe_metadata could not be pointed at a named dataset — the tool schema
   had no `dataset` parameter — and every payload was labelled "BrainSpan"
   regardless of which loader produced it. Asking "what metadata is in
   BrainSeq" got a refusal or BrainSpan's answer relabelled.

2. search_literature referenced ToolUniverse without importing it, so every
   call raised NameError; and the tool returned "papers" while the SvelteKit
   route read "results", so citations vanished in that UI even when the call
   worked.
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

from agent import TOOLS, dispatch_tool  # noqa: E402


def main() -> int:
    import main as app  # noqa: PLC0415 - after the stub is installed

    registry = app.registry
    loaded = registry.available
    print(f"datasets loaded    {len(loaded)}: {', '.join(loaded)}")

    # ── 1. the dataset argument must exist on the schema ──────────────────
    for tool_name in ("describe_metadata", "get_dataset_metadata"):
        schema = next(t for t in TOOLS if t["name"] == tool_name)
        assert "dataset" in schema["input_schema"]["properties"], (
            f"{tool_name} has no `dataset` parameter — the model cannot ask "
            "about a dataset that is not currently selected."
        )
    print("schema ok          both metadata tools accept `dataset`")

    # ── 2. each dataset profiles itself, and labels itself correctly ──────
    # Selection is deliberately a single dataset: describing another one must
    # not depend on it being selected.
    selection = [loaded[0]]
    seen_counts = {}
    for name in loaded:
        out = json.loads(dispatch_tool("describe_metadata", {"dataset": name},
                                       registry, selection))
        assert "error" not in out, f"{name}: {out['error']}"
        assert out["dataset"] == name, (
            f"payload for {name} is labelled '{out['dataset']}' — a mislabelled "
            "answer is worse than a missing one."
        )
        assert name in out["table"]["title"], (
            f"table title for {name} reads '{out['table']['title']}'"
        )
        assert out["variables"], f"{name} profiled zero variables"
        seen_counts[name] = (out["n_samples"], len(out["variables"]))

    print("per-dataset ok     " + ", ".join(
        f"{k} ({v[0]}s/{v[1]}v)" for k, v in list(seen_counts.items())[:4]) + " …")

    # The schemas genuinely differ, which is why one cannot substitute for
    # another. If they were identical this test would be proving nothing.
    var_counts = {v[1] for v in seen_counts.values()}
    assert len(var_counts) > 1, (
        "every dataset reported the same number of variables — the loaders are "
        "probably all reading the same metadata."
    )
    print(f"schemas differ ok  variable counts: {sorted(var_counts)}")

    # ── 3. get_dataset_metadata is scoped too ────────────────────────────
    for name in loaded[:3]:
        out = json.loads(dispatch_tool("get_dataset_metadata", {"dataset": name},
                                       registry, selection))
        assert out.get("dataset") == name, f"summary mislabelled for {name}"
    print("summary ok         get_dataset_metadata honours `dataset`")

    # ── 4. an unknown dataset is refused, not silently substituted ────────
    out = json.loads(dispatch_tool("describe_metadata", {"dataset": "Nonexistent"},
                                   registry, selection))
    assert "error" in out and "not loaded" in out["error"], (
        "an unknown dataset must be reported, never answered from another"
    )
    print("unknown ok         refused with the available list")

    # ── 5. literature search is wired and returns both key names ─────────
    lit = json.loads(dispatch_tool(
        "search_literature", {"gene_symbol": "SHANK3", "limit": 2},
        registry, selection))

    assert "results" in lit and "papers" in lit, (
        "search_literature must return both keys: the SvelteKit route reads "
        "`results`, the standalone page reads `papers`."
    )
    assert lit["results"] == lit["papers"], "the two keys disagree"
    assert "NameError" not in json.dumps(lit), (
        "NameError means ToolUniverse is referenced without being imported"
    )

    if lit.get("error"):
        # Acceptable outcome (offline, or ToolUniverse cannot write its cache),
        # but it must be reported rather than looking like "nothing published".
        print(f"literature         unavailable, reported: {lit['error'][:60]}…")
    else:
        assert lit["results"], "no error and no papers — silent empty result"
        for paper in lit["results"]:
            assert paper.get("title"), "paper with no title"
            assert paper.get("source") in ("PubMed", "EuropePMC")
        print(f"literature ok      {len(lit['results'])} papers "
              f"[{lit['results'][0]['source']}] {lit['results'][0]['title'][:40]}…")

    print("\nAll metadata-scope and literature checks passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

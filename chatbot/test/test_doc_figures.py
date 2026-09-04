"""
Cross-check the memory figures in the docs against a live measurement.

My previous check asserted only that the substring "217 MB" appeared somewhere
in HOSTING.md. It passed while the table said 217 MB and the config block three
lines below said 230 MB for the same configuration — a presence check cannot
catch a contradiction. This measures, then requires every quoted figure to match.
"""

import io
import contextlib
import os
import re
import resource
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("ANTHROPIC_API_KEY", "test-only-not-used")


def measure(datasets=None):
    """Peak RSS after startup and after exercising the tools, in MB."""
    if datasets:
        os.environ["BITHUB_REMOTE_DATASETS"] = datasets
    else:
        os.environ.pop("BITHUB_REMOTE_DATASETS", None)
    os.environ["BITHUB_REMOTE_DATA"] = "1"

    import anthropic
    anthropic.Anthropic = lambda *a, **k: type("C", (), {"messages": None})()

    rss = lambda: resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1e6
    with contextlib.redirect_stdout(io.StringIO()):
        import main
    startup = rss()

    from agent import dispatch_tool
    avail = main.registry.available
    for call, args in (("compare_datasets", {"gene": "SHANK3"}),
                       ("describe_metadata", {"dataset": avail[0]}),
                       ("get_developmental_trajectory", {"gene": "SHANK3"}),
                       ("generate_figure", {"gene": "SHANK3", "figure_type": "box"})):
        dispatch_tool(call, args, main.registry, avail)
    return len(avail), round(startup), round(rss())


def main_check() -> int:
    # One process can only load one configuration, so this checks the trimmed
    # recommendation — the figure a reader is most likely to act on.
    n, startup, loaded = measure("BrainSpan,BrainSeq,HDBR")
    print(f"measured           {n} datasets: {startup} MB startup, {loaded} MB under load")

    # The bundle annotation must be ONE object shared by every loader. It is a
    # property of the bundle (one row per gene, a presence column per dataset),
    # so a per-loader copy is pure duplication: it cost ~45 MB across eight
    # loaders and pushed all-eight past the 512 MB tier's usable headroom.
    # Checked by identity rather than by a memory threshold, because a
    # threshold on an 8-dataset run is slow and noisy while identity is exact.
    import main as app
    loaders = [app.registry.get(d) for d in app.registry.available]
    with_ann = [l for l in loaders if getattr(l, "annotation", None) is not None]
    if with_ann:
        shared = {id(l.annotation) for l in with_ann}
        if len(shared) != 1:
            failures_shared = (
                f"{len(with_ann)} loaders hold {len(shared)} distinct "
                "annotation tables; _bundle_annotation should memoise one per "
                "bundle"
            )
            print(f"  BAD {failures_shared}")
            return 1
        print(f"annotation shared  1 table across {len(with_ann)} loaders")

    doc = (HERE / "HOSTING.md").read_text()
    readme = (HERE / "README.md").read_text()

    failures = []

    # Every figure quoted for the 3-dataset config must be one of the two
    # measured values, within rounding tolerance.
    row = re.search(r"\|\s*3 \(BrainSpan, BrainSeq, HDBR\)\s*\|\s*(\d+) MB\s*\|\s*(\d+) MB", doc)
    if not row:
        failures.append("HOSTING.md has no 3-dataset table row in the expected shape")
    else:
        for label, quoted, actual in (("startup", int(row.group(1)), startup),
                                      ("under load", int(row.group(2)), loaded)):
            if abs(quoted - actual) > 5:
                failures.append(f"table {label} says {quoted} MB, measured {actual} MB")

    # No figure describing MEMORY for this config may contradict the
    # measurement. Scoped to sentences that mention the trimmed dataset list or
    # resident memory — "245 MB local data" is disk size and legitimately
    # different, so a blanket numeric sweep would flag it wrongly.
    memory_context = re.compile(
        r"[^.\n]*(?:BrainSpan,BrainSeq,HDBR|under load|resident|RSS|startup)[^.\n]*",
        re.I)
    for path, text in (("HOSTING.md", doc), ("README.md", readme)):
        for sentence in memory_context.findall(text):
            for value in {int(m) for m in re.findall(r"(\d{3}) MB", sentence)}:
                if abs(value - startup) > 5 and abs(value - loaded) > 5:
                    failures.append(
                        f"{path} quotes {value} MB in a memory context "
                        f"(\"{sentence.strip()[:60]}…\") but measurement is "
                        f"{startup} MB startup / {loaded} MB under load"
                    )

    for message in failures:
        print(f"  BAD {message}")
    if not failures:
        print("  ok  every quoted figure matches the measurement")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main_check())

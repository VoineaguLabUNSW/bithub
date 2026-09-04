"""Boot the FastAPI app in remote mode and exercise the tools through it."""
import os, sys, json
sys.path.insert(0, "/Users/arwanawaz/Documents/Projects/BITHub_2.0/bithub/chatbot")
os.environ["ANTHROPIC_API_KEY"] = "stub"
os.environ["BITHUB_REMOTE_DATA"] = "1"

import anthropic
class _B:
    def __init__(s, **k): s.__dict__.update(k)
class _R:
    def __init__(s, c, st): s.content, s.stop_reason = c, st
script = []
class _M:
    def create(s, **k): return script.pop(0)
class _S:
    def __init__(s, *a, **k): s.messages = _M()
anthropic.Anthropic = _S

import main
from fastapi.testclient import TestClient
c = TestClient(main.app)

h = c.get("/api/health").json()
print("data_source:", h["data_source"], "| genes:", h["n_genes"], "| samples:", h["n_samples"])

# every tool, through the dispatcher, against the live bundle
from agent import dispatch_tool
for name, args in [
    ("get_expression", {"gene": "SHANK3"}),
    ("get_developmental_trajectory", {"gene": "SHANK3"}),
    ("get_variance_partition", {"gene": "SHANK3"}),
    ("describe_metadata", {"variable": "PMI (hours)"}),
    ("get_dataset_metadata", {}),
    ("search_genes", {"query": "SHAN"}),
    ("generate_figure", {"gene": "SHANK3", "figure_type": "trajectory"}),
    ("generate_figure", {"gene": "CTNNB1", "figure_type": "scatter",
                         "x": "AgeNumeric", "color_by": "Regions", "symbol_by": "Period"}),
    ("generate_figure", {"figure_type": "heatmap",
                         "genes": ["SHANK3", "MECP2", "FOXP2"]}),
    ("compare_datasets", {"gene": "SHANK3"}),
]:
    out = json.loads(dispatch_tool(name, args, main.registry, ["BrainSpan"]))
    err = out.get("error")
    tag = "ERROR: " + str(err)[:50] if err else "ok"
    extra = ""
    if name == "get_expression": extra = f"n={out.get('n_samples')}"
    if name == "get_developmental_trajectory": extra = f"peak={out.get('peak',{}).get('age_interval')}"
    if name == "generate_figure": extra = f"{out.get('figure_type')} traces={len(out.get('plotly_data',[]))}"
    if name == "compare_datasets": extra = f"z={out['results'][0]['zscore']}"
    print(f"  {name:<32}{tag:<12}{extra}")

# cell-type-controlled must be refused, not silently wrong
out = json.loads(dispatch_tool("get_variance_partition",
      {"gene": "SHANK3", "cell_type_controlled": True}, main.registry, ["BrainSpan"]))
print("\ncell_type_controlled ->", str(out.get("error"))[:80])

print("\nrange requests issued:", main.loader.remote._fetch_row.cache_info())
print("REMOTE SERVICE TESTS PASSED")

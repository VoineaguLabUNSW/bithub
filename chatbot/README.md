# Ask BITHub — chat backend

Conversational access to the BrainSpan expression data behind BITHub. A
FastAPI service runs an Anthropic tool-calling loop against the expression
matrix, the variancePartition results and PubMed/EuropePMC, and serves a
standalone chat page.

**Status: local prototype.** The service holds an Anthropic API key. It is
open by default for local use; set `BITHUB_ACCESS_TOKEN` before exposing it
anywhere (`share.sh` does this for you). The link on the BITHub
home page is `dev`-gated and does not appear in the production static build.
Read [Deployment](#deployment) before exposing it.

---

## Quick start

### Showing it to someone — one command

```bash
./demo.sh
```

Builds the site with the chat entry point enabled and serves the whole thing
— pages *and* API — from the single FastAPI process on
<http://localhost:8000>. Same origin, so no CORS, no second terminal, no
`VITE_CHAT_API`. The home page gets an "Ask BITHub" pill; `/ask` is the chat.

This is a demo path, not how the site ships: production keeps the frontend
static on S3/CloudFront with the API behind its own URL and a rate limit.

### Sharing it over ngrok

```bash
./share.sh
```

Builds, starts the backend, opens the tunnel, and prints a link with an
access key already in it:

```
https://<random>.ngrok-free.app/ask?k=<generated-key>
```

The key is read from `?k=`, stored in `sessionStorage`, and stripped from the
address bar; every later request sends it as `X-BITHub-Token`. Requests
without it get 401.

**Why a key is mandatory here.** `/api/chat` calls the Anthropic API, so an
open public URL spends your credits for whoever finds it, and ngrok
subdomains are actively scanned — a random URL is not a secret. CORS does not
help: it is a browser policy, and `curl` ignores it completely.

Default caps, both overridable: **20 questions/hour per IP**,
**200/day total**. They are in-memory, so they reset on restart and are
per-process; adequate for a shared demo, not for a permanent deployment.
`/api/health` reports `access_token_required`, the limits, and
`questions_today`.

What this is not: authentication. Anyone you send the link to can spend
credits, and the key travels in a URL. Stop the tunnel when you are done, and
generate a fresh key for the next share (the script does that automatically
unless you set `BITHUB_ACCESS_TOKEN` yourself).

| Variable | Default | Purpose |
|---|---|---|
| `BITHUB_ACCESS_TOKEN` | unset (open) | Require this key on `/api/chat` |
| `BITHUB_RATE_PER_IP_HOUR` | 20 | Per-visitor hourly cap |
| `BITHUB_RATE_TOTAL_DAY` | 200 | Whole-instance daily cap |

Read endpoints (`/api/health`, `/api/datasets`, the site itself) stay open so
the page loads for anyone with the link.

### Developing — two terminals

Use this when you are changing frontend code and want hot reload.

**Terminal 1 — backend** (must run from `chatbot/`, so `main` is importable):

```bash
cd chatbot
.venv/bin/uvicorn main:app --reload --port 8000
```

Wait for `Application startup complete`. Loading the matrices takes about a
second; a failure names the missing file rather than dying on first question.
Sanity check: `curl localhost:8000/api/health`.

**Terminal 2 — frontend:**

```bash
cd frontend
npm run dev
```

Open <http://localhost:5173> and click the **Ask BITHub** pill under the
search box, or go straight to <http://localhost:5173/ask>. `vite dev` always
shows the pill regardless of `VITE_SHOW_CHAT`.

The single-file chat page at <http://localhost:8000/standalone> needs no
frontend build at all — useful for testing the backend alone.

### How the frontend finds the backend

Two build-time flags, both in `frontend/.env` (see `.env.example`), read
through `src/lib/config.js`:

| Variable | Default | Effect |
|---|---|---|
| `VITE_CHAT_API` | `http://localhost:8000` | Backend base URL. Irrelevant when one process serves both — the page is same-origin. |
| `VITE_SHOW_CHAT` | unset (false) | Shows the home-page entry point in a **production** build. Keep false for the GitHub Pages deploy. |

Plain `import.meta.env`, deliberately, rather than either SvelteKit env
module. `$env/static/public` **fails the build outright** when a variable is
unset, so CI on a clean checkout breaks. `$env/dynamic/public` reads from a
server at runtime, and `adapter-static` has no server — it resolves to an
empty object, so the variable silently never applies and a deployed build
quietly falls back to localhost. Both were tried here; both were wrong.

Verified by rendering the compiled component: unset gives no link,
`VITE_SHOW_CHAT=true` gives the link.

### First-time setup

```bash
cd chatbot
python -m venv .venv && .venv/bin/pip install -r requirements.txt
cp .env.example .env          # then add your ANTHROPIC_API_KEY
.venv/bin/python scripts/build_parquet.py     # one-off, ~10s

cd ../frontend
npm install --legacy-peer-deps
```

`--legacy-peer-deps` is required: SvelteKit 1.30.4 wants Vite ^4 while
`package.json` pins ^5. Bun (which CI uses) tolerates the conflict; npm does
not. This is pre-existing, unrelated to the chat.

### Checks that need no API key

```bash
cd chatbot
.venv/bin/python test_agent.py          # loader, tables, figures, z-scores
.venv/bin/python test_remote_loader.py  # CloudFront bundle reads
.venv/bin/python test_metadata_scope.py # per-dataset metadata, literature wiring
.venv/bin/python test_cell_types.py     # cell-type tool, units, dataset routing
.venv/bin/python test_new_tools.py      # diagnosis, correlation, composition, locus
.venv/bin/python test_doc_figures.py    # numbers quoted in this README
cd ../frontend && npm run build         # static build must stay clean
```

`test_cell_types.py` and `test_new_tools.py` need the network (they read the
published bundle for all eight datasets). Both validate **behaviour rather
than numbers** — canonical marker *rank* (GFAP in astrocytes, P2RY12 in
microglia, GAD1 in inhibitory neurons), donor-level aggregation, and the
wording of each refusal — because the bundle is re-cut periodically and
anything pinned to a level name or a p-value becomes a false alarm.

That is not hypothetical. The **31 Aug 2026 freeze** renamed HCA's `Class`
column, and a hardcoded `resolution="Class"` assertion in
`test_cell_types.py` broke; it now discovers the finer grouping at runtime
and asserts the biology without naming a level. The same freeze dropped
HDBR's all-control `Diagnosis` column, so `compare_by_diagnosis` refuses via
a different branch — the test accepts either, provided the refusal names a
dataset that does work.

**If every dataset suddenly fails on `zlib.error: incorrect header check`,
the cached index is stale**, not the code. `cache/out.hdf5` is downloaded
once; when the bundle is re-uploaded, old row offsets point into the middle
of the new `expression.bin`. The byte-length check still passes, which is
why the failure surfaces at decompression. Delete `cache/out.hdf5` and let
it re-download.

The marker table is split by dataset age, and the reason is biological
rather than technical: Cameron is 13-15pcw, where mature astrocytes and
oligodendrocytes do not yet exist, and GFAP, AQP4 and PLP1 top out in
**radial glia**. Asserting "GFAP is highest in astrocytes" would fail there
correctly, so the fetal set gets progenitor markers (SOX2 in cycling
progenitors, EOMES in intermediate progenitors, OLIG1 in OPCs) and the
glial markers reassigned to the progenitor that expresses them at that
stage.

---

## When it does not start

| Symptom | Cause and fix |
|---|---|
| `Address already in use` | An older server is still running. `lsof -nP -iTCP:8000 -sTCP:LISTEN` to find it, then `kill <pid>` — or use `--port 8001` and set `VITE_CHAT_API` to match. |
| `ANTHROPIC_API_KEY is not set` | No `.env`, or the key line is missing. `cp .env.example .env` and add it. |
| `Startup failed … missing` | A data file is absent. The message names it; check `chatbot/data/`. |
| `ModuleNotFoundError: main` | uvicorn was started outside `chatbot/`. `cd chatbot` first. |
| Amber "backend unreachable" on `/ask` | The backend is down, or on a different port than `VITE_CHAT_API`. |
| CORS error in the browser console | The frontend origin is not in `BITHUB_ALLOWED_ORIGINS`. Defaults cover ports 5173 and 8000 on both `localhost` and `127.0.0.1`. |
| Frontend `npm install` peer-dep error | Add `--legacy-peer-deps` (see above). |

A restart is needed after editing `data_loader.py` or `agent.py` if you did
not pass `--reload`; the matrices reload in about a second either way.

---

## Where the data comes from — and an unverified assumption

Everything is read from local files at startup; there is no database and no
network call for expression data.

```
DATA_DIR = $BITHUB_DATA_DIR  or  chatbot/data/   (default, resolved from __file__)
```

Because the paths anchor to `__file__` rather than the working directory,
only `main` needs to be importable. `chatbot/data/` is gitignored, so these
files travel out of band and are not in the repo.

The expression matrix is the one path with a choice in it: `data_loader`
swaps `.csv` for `.parquet` and uses the parquet **if it exists**, falling
back to the CSV otherwise. `EXPR_PATH` therefore names the CSV even though
the parquet is what actually loads.

### Reading the CloudFront bundle — implemented and verified live

`remote_loader.py` does this today. `test_remote_loader.py` exercises it
against the real published bundle:

```bash
.venv/bin/python test_remote_loader.py
```

It downloads `out.hdf5` (15.3 MB) into `cache/`, then pulls individual gene
rows out of `expression.bin` — **3.45 GB** — by HTTP Range request. That size
is the whole argument for range reads: the browser never downloads it either.

No new architecture was needed. The browser's path maps directly onto Python:

| Browser | Python |
|---|---|
| `jsfive` reads `out.hdf5` | `h5py` |
| `pako` inflate | `zlib` (stdlib) |
| `data_pb.js` decode | `pipeline/data_pb2.py` (already generated) |
| `fetch` with `Range:` | `requests`, same header |

`BITHubRemoteLoader` mirrors `BrainSpanLoader`'s surface, so
`DatasetRegistry` can hold either without the tools in `agent.py` changing.
Rows are LRU-cached — immutable between pipeline runs.

#### Three things the live bundle taught us

**1. `chatbot/data/` really does match the published data.** Expression values
for SHANK3, ACTB, GAPDH, GFAP, FOXP2 and MECP2 are identical between the local
parquet and the bundle. The provenance worry recorded earlier in this file is
resolved: same numbers.

**2. The local z-scores do not match the published ones, and cannot.** ACTB is
`+3.595` locally but `+3.109` in the bundle. The transform is right; the
*population* differs — the pipeline standardises across the **30,687** genes it
writes for BrainSpan, while the local matrix has **52,376** rows, so the
reference mean and SD differ. Restricting the local computation to the bundle's
gene set reproduces the published values to within 0.02 for **99.7%** of genes
(r = 0.9984, n = 30,257).

So the local `gene_zscore` is fine for ranking and within-service comparison,
but must not be presented as the number on a gene-view axis. Read
`metadata/<dataset>/zscores/All` for that — which is what
`BITHubRemoteLoader.gene_zscore` returns.

**3. The URL fields inside `metadata.json` are unusable — and unused.** The
copy at `/bithub/metadata.json` on CloudFront carries Windows local paths:

```
data_url: 'http://localhost:5501\\..\\output-final-feb\\out.hdf5'
```

left behind by a `deploy_local: True` run. The same stale path is embedded in
the HDF5 as the `path` attribute on `metadata/BrainSpan/matrices/RPKM`.

Neither the site nor the chat reads those fields any more. Since commit
062f92e the frontend derives both artefacts as **siblings** of the `?source=`
URL — `$metadata.url + '/out.hdf5'`, `$metadata.url + '/expression.bin'` — and
`chatbot/source.py` implements the same rule server-side. The location of
`metadata.json` *is* the address; what is written inside it is ignored. That
commit also deleted `frontend/static/metadata.json`, which the backend used to
read, so the sibling rule is now the only mechanism on either side.

`BITHubRemoteLoader` still refuses an *embedded* `localhost`/backslash URL with
an explanatory error rather than attempting it. The check applies only to the
value read out of the bundle — a `bin_url=` you pass deliberately is honoured,
including a `file://` one, because a bundle on disk is a supported source.

#### Bundle layout, as actually published

```
data/{Ensembl ID, Gene Symbol, <Dataset>}   34,440 genes; per-dataset row map
metadata/<Dataset>/matrices/RPKM            (30687, 2) int64 byte ranges
metadata/<Dataset>/zscores/{All,Cortex,…}   precomputed, per region
metadata/<Dataset>/samples/*                18 metadata columns
metadata/<Dataset>/variance_partition       varPart ranges
```

Note `matrices/RPKM` is 2-D `(n_rows, 2)`, not the flat array an older
revision wrote; the loader handles both.

#### Switching the service over

`./demo.sh` from the repo root now runs in this mode by default — the site and
the chat on one port, reading the published bundle:

```bash
./demo.sh                    # http://localhost:8000/ask
REMOTE=0 ./demo.sh           # local CSV/parquet instead (BrainSpan only)
```

Or the backend alone:

```bash
cd chatbot
.venv/bin/uvicorn main:app --port 8000          # published bundle (default)
BITHUB_LOCAL_DATA=1 .venv/bin/uvicorn main:app --port 8000   # local files
```

Exactly one source is loaded: in the default remote mode the local CSV/parquet
is never opened, so the 150 MB matrix need not be present. Startup is ~2.4 s
against ~4 s for the local path.

On first start it caches `out.hdf5` (15.3 MB) into `chatbot/cache/`, then
fetches gene rows on demand. `/api/health` reports
`"data_source": "published_bundle"` so you can tell which mode is live.

**The bundle is the default** so the chat and the site resolve every number
from identical bytes. Two differences from the local files are worth knowing,
both measured against the live bundle:

- **z-scores** are the bundle's published values — the ones the gene view
  plots — and run ~0.30 higher than locally recomputed ones, because the local
  path standardises over all 52,376 genes in the matrix and the bundle over the
  30,687 it publishes. Rank order is unaffected (r = 1.00000), so "is this gene
  high or low" is unchanged; the absolute number moves.
- **the cell-type-controlled variance-partition model is not in the bundle.**
  Requesting it raises instead of quietly returning the standard model. It
  exists only in `BrainSpan_varPart_cellTypes.csv`, so use
  `BITHUB_LOCAL_DATA=1` for that model.

Per-sample expression values are **identical** between the two sources, as is
the 524-sample set.

`build_remote_brainspan_loader` returns something satisfying the same contract
`BrainSpanLoader` does, so **nothing in `agent.py`, the tools, or the registry
changed.** All ten tools were exercised against the live bundle
(`test_remote_service.py`): expression, trajectory, varPart, metadata,
search, all three figure types, and cross-dataset comparison.

Expression and varPart rows are fetched lazily per gene — `expr` is a shim
whose `.loc` triggers one cached Range request rather than holding a matrix in
memory.

Measured latency:

| | |
|---|---|
| First question about a gene | **~1.7 s** |
| Same gene again (LRU cached) | **~11 ms** |
| Startup | 15 MB download once, then ~instant |

So a conversation pays about 1.7 s the first time each gene comes up. Rows are
immutable between pipeline runs, which is what makes caching safe.

#### All eight datasets, which is the real payoff

Remote mode registers **every published dataset**, not just BrainSpan — the
bundle carries all of them, so cross-dataset questions become answerable for
the first time. Measured, reading SHANK3 from each:

| Dataset | Samples | Bytes fetched | Read |
|---|---:|---:|---:|
| BrainSpan | 524 | 1,932 | 79 ms |
| BrainSeq | 900 | 3,231 | 102 ms |
| HDBR | 649 | 2,351 | 90 ms |
| GTEx | 2,642 | 7,474 | 82 ms |
| PsychENCODE | 1,369 | 4,914 | 80 ms |
| Cameron | 69,284 | 27,854 | 90 ms |
| HCA | 46,958 | 132,091 | 182 ms |
| Velmeshev | 81,215 | 47,303 | 121 ms |

One gene across all eight costs **0.23 MB and about 1 second** — against 3,454
MB to download `expression.bin` whole. That ratio is the whole design.

Note the single-nucleus sets work fine: Velmeshev's 81,215 cells arrive in
47 KB because the row is one gene's values, not a matrix.

`compare_datasets` now returns eight rows, and the z-score column is what
makes them comparable — the raw `mean log2` spans **+5.68 (GTEx, TPM)** to
**−3.46 (Cameron, CPM)** for the same gene, purely because the units differ.
Comparing those numbers directly would be meaningless; comparing z-scores is
not.

In the UI each dataset is a chip; **BrainSpan is preselected and `all` widens
to every loaded dataset in one click.** Selecting all eight by default would
turn every question into a cross-dataset query — one Range request per dataset
— when most questions concern one. The header shows `8 datasets · 34,440 genes
· published bundle` so the active source is never ambiguous.

Narrow the server-side set with `BITHUB_REMOTE_DATASETS=BrainSpan,GTEx` if
eight is more than you want. A dataset the bundle lacks is reported at startup and marked
unavailable rather than aborting the run.

#### Two things remote mode does NOT give you

**Cell-type-controlled variance partition is unavailable.** The bundle carries
one varPart model and it is not the deconvolved one. Asking for
`cell_type_controlled=True` raises an explanatory error rather than returning
the standard model under the wrong label.

**The bundle's varPart differs from both local files.** For SHANK3, Period is
`0.615` in the bundle vs `0.679` (`BrainSpan_varPart.csv`) and `0.603`
(`…_cellTypes.csv`). Across eight spot-checked genes the mean absolute
difference is ~0.13, and GFAP differs by 0.39 (`0.136` vs `0.522`). These are
separate variancePartition runs, not a formatting artefact.

That is a genuine ambiguity in the data, not a bug in either loader — but it
means the *variance* numbers change when you flip the flag, while expression
values do not. The bundle's are the ones the gene view plots, which is the
argument for preferring them; worth confirming with whoever produced the
December bundle which run is authoritative.

### These files are not the site's files

The deployed site does not read anything here. It fetches
`https://d33ldq8s2ek4w8.cloudfront.net/bithub/out.hdf5` plus per-dataset
matrices such as `BrainSpan_RPKM.csv.gz`, produced by `pipeline/main.py` from
sources listed in `pipeline/input.yaml` — which currently points at
`./test_data` with `BrainSeq-*-example.csv` fixture filenames, not at these
matrices. Nothing in `pipeline/` references `chatbot/data/`.

**Update: now verified.** Expression values for six spot-checked genes are
identical between `chatbot/data/` and the published bundle, so the two halves
of BITHub do agree on the underlying numbers. The z-scores differ, for the
gene-population reason described above — not because the data differs.

---

## Data files

Five files in `chatbot/data/` (gitignored — they are large and not
redistributable). Override the location with `BITHUB_DATA_DIR`.

| File | Contents |
|---|---|
| `BrainSpan-exp.csv` | RPKM matrix, 52,376 genes x 524 samples |
| `BrainSpan-exp.parquet` | Generated by `scripts/build_parquet.py` |
| `BrainSpan-metadata.csv` | 524 samples x 19 columns |
| `BrainSpan_varPart.csv` | variancePartition, 19,641 genes x 10 covariates |
| `BrainSpan_varPart_cellTypes.csv` | Same, with cell-type fractions as covariates |
| `gene_annotation.csv` | Ensembl ID, symbol, name, Entrez ID |

The service refuses to start if any are missing, naming the file rather than
failing on the first question.

### Why parquet

The CSV is 158 MB and is re-parsed on every reload. Converting once cuts load
time from 0.86s to 0.05s (warm cache, best of 3; roughly 3x on a cold read)
and on-disk size from 158 MB to 87 MB, storing RPKM as float32. `data_loader`
uses the parquet automatically when present and falls back to the CSV with a
warning.

### Column naming

The R pipeline exports display-formatted headers — `Age (Numeric)`,
`Proportion of Neurons (MultiBrain)` — and variancePartition wraps names
containing spaces in backticks (`` `PMI (hours)` ``). These are normalised
once at load time via `METADATA_COLUMNS` in `data_loader.py`. Add a dataset by
extending that map, not by renaming at the call site.

---

## API

Both `/chat` and `/api/chat` work; prefer `/api/chat`.

### `POST /api/chat`

```jsonc
{
  "message": "Does SHANK3's postnatal rise hold up in other cohorts?",
  "history": [{"role": "user", "content": "..."},
              {"role": "assistant", "content": "..."}],
  "datasets": ["BrainSpan", "BrainSeq"]
}
```

`message` is 1–2000 characters. `history` is the prior turns, sent by the
client on every request — the server keeps no session state. `datasets` is
the user's current selection; omit it for all loaded datasets. Ids that are
not loaded come back in `datasets_unavailable` rather than being ignored, and
a selection containing no loaded dataset returns 400.

```jsonc
{
  "response":   "markdown text",
  "last_gene":  "SHANK3",          // null when no gene was resolved
  "figure":     { /* first figure, back-compat */ },
  "figures":    [ { "figure_type": "developmental_trajectory",
                    "plotly_data": [...], "plotly_layout": {...},
                    "caption": "..." } ],
  "tables":     [ { "type": "table", "title": "...", "columns": [...],
                    "rows": [...], "highlight_row": 7, "footnote": "..." } ],
  "literature": { "papers": [ {"title","authors","journal","year","doi","url","open_access"} ] },
  "tools_used": ["compare_datasets"],
  "datasets_used": ["BrainSpan"],
  "datasets_unavailable": [{"dataset":"GTEx","reason":"not yet loaded into the chat service"}],
  "elapsed_ms": 8432
}
```

`plotly_data` and `plotly_layout` pass straight to `Plotly.newPlot`. Errors
return `{"detail": "..."}` with a 500; a malformed request returns 422.

### `GET /api/datasets`

Lists all eight BITHub datasets with an `available` flag; only BrainSpan is
`true`. The UI renders the rest as disabled options so the scope of the
service is visible rather than implied.

### `GET /api/health`

```jsonc
{"status":"ok","dataset":"BrainSpan","n_genes":52376,
 "n_samples":524,"model":"claude-sonnet-4-6","unit":"log2(RPKM+1)"}
```

---

## Tools available to the agent

| Tool | Returns | `dataset` |
|---|---|---|
| `get_expression` | Means by stratum and by region x stratum | yes |
| `get_cell_type_expression` | Means per cell type, single-nucleus sets only | yes |
| `get_developmental_trajectory` | Means per age interval, **transitions ranked by magnitude**, peak | yes |
| `get_variance_partition` | Components, ranked, with technical total pre-summed | yes |
| `get_dataset_metadata` | Sample and gene counts, regions, periods, coverage caveat | yes |
| `describe_metadata` | Per-variable type, range or categories, **and completeness** | yes |
| `compare_datasets` | One gene across datasets on the z-scored scale, with an explicit unavailable list | no — takes `datasets` |
| `search_genes` | Symbol search, prefix matches first | yes |
| `generate_figure` | Plotly spec — `expression`, `trajectory`, `variance`, `scatter`, `heatmap`, `box`, `composition`, `composition_pie` | yes |
| `compare_by_diagnosis` | Case/control per diagnosis, **tested on donor means**, effect size, group ns | yes |
| `compare_cell_type_by_diagnosis` | The same within each cell type, largest difference named | yes |
| `correlate_with_covariate` | Gene vs every numeric covariate, ranked by \|rho\|, with direction | yes |
| `correlate_genes` | Two genes across samples, Spearman, direction | yes |
| `get_cell_type_composition` | MultiBrain deconvolution proportions, optionally per stratum | yes |
| `find_genes_in_locus` | Genes in a coordinate window, position-ordered | yes |
| `gene_info` | Symbol, Ensembl ID, description, hg38 locus, **which datasets carry it** | yes |
| `search_literature` | PubMed + EuropePMC via ToolUniverse | no — external |

Seven of these came out of the data-depth survey
(`bithub_data_depth_tools.md`), which measured what the published bundle can
actually answer. Two things in that list are worth reading before extending it:
the **`statistical_note` contract** (below) and the **pseudoreplication guard**
(§ *Nuclei are not donors*).

### `statistical_note`: the caveat travels with the payload

`compare_by_diagnosis`, `compare_cell_type_by_diagnosis`,
`correlate_with_covariate`, `correlate_genes` and `get_cell_type_composition`
all return:

```python
"statistical_note": {
    "unit_of_analysis": "donor",       # or "sample", "donor x cell type"
    "n_observations": 81215,           # what was measured
    "n_donors": 31,                    # what was tested
    "aggregated_to_donor": True,
    "warnings": [...],
    "text": "One sentence the model is told to lift verbatim.",
}
```

The model reliably repeats what a payload tells it and reliably omits what it
does not. A p-value with no unit of analysis attached is the failure mode these
tools were built to close, so the caveat is a **field**, not a docstring — and
`chatfigure.svelte` renders `text` under the figure so it survives a
screenshot.

### Nuclei are not donors

Velmeshev has 81,215 nuclei from 31 donors. A t-test on nuclei answers "are
these two piles of nuclei different", which they always are: SHANK3 in ASD
gives p ~ 1e-3 at nucleus level and p ~ 0.56 on donor means. Every inferential
tool therefore aggregates to donor level when observations per donor exceed
`PSEUDOREPLICATION_RATIO`, reports both counts, and says so in
`statistical_note.text`. `test_new_tools.py` asserts the aggregation happened
and that the ASD p-value is *not* significant — a nucleus-level test leaking
through would produce a wrong answer with a plausible number attached, which
is the worst failure mode this chat has.

### Two refusals that are features

`generate_figure(figure_type="composition_pie", group_by=...)` refuses: several
pies cannot be compared by eye, and a stacked bar shares a baseline. A single
donut is allowed for the ungrouped case.

`find_genes_in_locus` and `gene_info` need the bundle's `/data` annotation
table, which only the published-bundle path has. On the local-CSV path they
refuse with that explanation rather than inventing coordinates.

### Every per-gene tool declares `dataset`

`dispatch_tool` has always routed on `args["dataset"]`, but for a long time
only three tools *declared* the parameter. The model therefore could not
name a dataset and silently got `selection[0]` — while the system prompt
told it to pass one. The property is now defined once
(`agent._DATASET_PROPERTY`) and attached by a loop over
`_PER_DATASET_TOOLS`, with an assertion at import time so a typo in that set
fails loudly rather than leaving a schema unpatched.

Two tools deliberately do **not** take it: `compare_datasets` takes a
`datasets` list, and `search_literature` is not dataset-scoped. Declaring
the singular form on either would invite a call the dispatcher cannot
honour.

### Cell types — a separate tool, not a `get_expression` argument

The eight datasets split into two families that are resolved on different
axes:

- **Bulk tissue** (BrainSpan, BrainSeq, HDBR, GTEx, PsychENCODE) — one
  value per sample, each sample a *mixture* of cell types, with
  developmental and regional axes.
- **Single-nucleus** (Cameron, HCA, Velmeshev) — one value per nucleus,
  labelled by cell type, with **no developmental period**.

`get_expression` used to group by `Period` unconditionally, so all three
single-nucleus datasets raised `KeyError: 'Period'` on the most basic query
— three of eight datasets crashed. It now picks the finest available
stratum from `_EXPRESSION_STRATA` (`Period`, then `AgeInterval`), and
returns region means alone when a dataset has no developmental axis at all.
`grouped_by` in the payload names which stratum was used, and the result
table builds its columns from the levels actually present rather than
assuming Prenatal/Postnatal — otherwise the single-nucleus tables rendered
as empty cells with the real numbers stranded elsewhere in the payload.

`get_cell_type_expression` is the tool for the cell-type axis. It groups by
`MajorCellType` by default — the only annotation column all three
single-nucleus sets share — and reports `vs_dataset_mean`, each cell type's
difference from the gene's mean across all nuclei, so "enriched" is a
number rather than an impression.

**Cell-type levels are discovered at runtime, never hardcoded.** They are
not stable across pipeline freezes: Cameron's are `OPC`/`Endothelial` in
one and `OPCs`/`Endothelia` in another. `cell_type_levels()` reads them
from the loaded metadata, and a rejected `cell_type` argument lists what is
actually available.

On a bulk dataset the tool **refuses** and names `get_variance_partition`
instead. That refusal is the point: variance explained by an astrocyte
*proportion* and expression *within* astrocytes are different claims, and
silently answering the first when asked the second would be a wrong answer
in a plausible format.

### Units are per-dataset, and were previously wrong

Every payload used to be labelled `log2(RPKM+1)` and attributed to
BrainSpan, because both strings were hardcoded rather than read from the
loader. BITHub's datasets are a mix: RPKM (BrainSpan, BrainSeq, HDBR), TPM
(GTEx, PsychENCODE), CPM (Cameron, HCA, Velmeshev). A TPM value reported as
RPKM is a wrong number wearing a plausible unit, which is harder to catch
than an error. `BrainSpanLoader.matrix_name` and `.dataset_id` now carry
these, `build_remote_brainspan_loader` sets them per dataset, and
`test_cell_types.py` asserts the expected unit for all eight.

Because the dataset name is in every table title, per-dataset tables no
longer collide in the UI's title-keyed dedupe.

### Figures

Six types. Two are fixed-shape (`expression`, `variance`); `trajectory` is
fixed but ordered developmentally; **`scatter`, `heatmap` and `box` are
configurable**, which is the point — they take metadata column names as
arguments rather than hardcoding an encoding.

`box` exists because `trajectory` plots means and a mean hides its spread: 4.9
from tight replicates and 4.9 from a bimodal distribution look identical on a
line. It draws the per-sample distribution for any categorical column, with an
optional `split_by` for grouped boxes, and flags groups with fewer than five
samples in the caption. `test_agent.py` asserts each box's mean equals the
trajectory's value for that interval — two figures disagreeing about the same
gene is exactly what destroys trust in a grounded assistant.

```python
generate_figure(gene="SHANK3", figure_type="box")                       # by age interval
generate_figure(gene="SHANK3", figure_type="box",
                group_by="Regions", split_by="Period")                  # grouped
```

```python
# "numeric age on x, shape by period, colour by region"
generate_figure(gene="CTNNB1", figure_type="scatter",
                x="AgeNumeric", color_by="Regions", symbol_by="Period")

# any numeric column works as x
generate_figure(gene="GFAP", figure_type="scatter", x="RIN", color_by="Sex")

generate_figure(figure_type="heatmap", genes=["SHANK3","MECP2","FOXP2"],
                group_by="AgeInterval", scale="zscore")
```

`x` must be numeric; `color_by` (≤12 levels) and `symbol_by` (≤6) must be
categorical. Violations raise a `ValueError` naming the valid columns, which
reaches the model as a tool error it can act on — so a bad encoding produces
a corrected retry rather than a refusal.

Scatter emits one trace per colour × symbol combination so the legend shows
both encodings; a 3-region × 2-period plot is 6 traces covering all 524
samples. Heatmap z-scores each gene across groups by default (`scale="raw"`
for log2(RPKM+1)) and returns a matching table.

Note `AgeNumeric` is years relative to birth — prenatal samples are negative
and bunch near zero on a linear axis. The caption says so, and `log_x` is
refused for that column rather than silently dropping points.

### Asking about a specific dataset

`describe_metadata` and `get_dataset_metadata` both take a `dataset` argument,
so "what metadata is in BrainSeq?" works regardless of which chips are
selected — the selection governs gene queries, not what may be described.

This did not work until it was tested by asking. Three defects:

- The tool schemas had no `dataset` parameter, so the model could not name one
  even though `dispatch_tool` already honoured it.
- Every payload was labelled `"dataset": "BrainSpan"` — hardcoded in two
  places — so BrainSeq's metadata came back claiming to be BrainSpan's. A
  mislabelled answer is worse than a missing one. `DatasetRegistry` now sets
  `loader.dataset_id`.
- `get_dataset_metadata` read `Regions`, `Period`, `AgeNumeric` and
  `StructureAcronym` unconditionally and crashed on five of eight datasets.

**The schemas genuinely differ**, which is why one cannot stand in for another:

| Dataset | Samples | Metadata columns | varPart |
|---|---:|---:|---|
| BrainSpan | 524 | 18 | yes |
| BrainSeq | 900 | 32 | yes |
| HDBR | 649 | 40 | yes |
| GTEx | 2,642 | 48 | yes |
| PsychENCODE | 1,369 | 19 | yes |
| Cameron | 69,284 | 6 | no |
| HCA | 46,958 | 16 | no |
| Velmeshev | 81,215 | 18 | no |

The three single-nucleus datasets carry **no variance_partition group** in the
bundle. That is now reported as absent; previously it raised `KeyError` and
reached the user as `Missing required argument: "Unable to synchronously open
object"`.

`test_metadata_scope.py` covers all of this, including an assertion that the
variable counts are not all equal — if they were, the test would be passing
while every loader read the same metadata.

### Literature search (ToolUniverse)

Still present, and now actually working. `search_literature` queries PubMed and
EuropePMC through ToolUniverse 1.3.1 (~2,600 tools registered), deduplicates by
title, and returns titles, years, journals, DOIs and URLs.

It had been broken since the `data_loader` rewrite: `ToolUniverse` was
referenced in `get_tu()` but never imported, so every call raised `NameError`.
Two further problems sat behind it — the tool returned `papers` while the
SvelteKit route read `results`, so citations rendered on the standalone page and
silently vanished in `/ask`; and both source failures were `print()`ed to the
server log and returned as an empty list, which reads to a user as "nothing is
published" rather than "the lookup failed".

Now: the import is lazy (it pulls in `fastmcp` and takes seconds, so startup
should not pay for it unless a literature question is asked), both key names are
returned, failures come back in an `error`/`errors` field, the UI shows an
unavailable notice, and prompt rule 16a forbids filling the gap from
recollection.

First call in a process takes ~8 s while the tool registry loads; subsequent
calls are fast. ToolUniverse writes a cache to `~/.tooluniverse`.

### Answer formatting

Assistant output is markdown, rendered through `frontend/src/lib/utils/markdown.js`
— `marked` for parsing, `DOMPurify` for sanitising. Before this the chat showed
the text verbatim, so a structured answer arrived with literal `##` and
`|---|---|` on screen.

Rendering model output as HTML means trusting it enough to reach `innerHTML`, so
the allowlist has no `script`, `style`, `iframe`, `form` or event handlers, and
`javascript:` URLs are stripped. `src/lib/utils/markdown.test.mjs` covers eight
injection vectors plus the structural cases:

```bash
cd frontend && node src/lib/utils/markdown.test.mjs
```

Two things worth knowing if you touch this. **DOMPurify must be bound to a real
DOM** — it reports `isSupported: false` otherwise and `sanitize` is undefined,
so the renderer fails closed to escaped plain text rather than passing raw HTML
through. And the tests use **jsdom, not linkedom**: against linkedom DOMPurify
reports unsupported and passes `<script>` straight through, which would make
every injection test pass while proving nothing. The test file asserts
`isSupported` before running for that reason.

The system prompt (rules 5a, 17a–17c) tells the model to open with one bold
finding sentence, organise evidence under `##` headings named for what they
establish, and never hand-write a markdown table — tools return tables, and a
hand-built one is both a transcription risk and the main source of unreadable
output.

### Variance decomposition — a bar, not a table

Variance results render as a **proportion bar**: one horizontal bar whose
segments sum to 1, with every component and percentage in the legend beneath.

The reasoning is that variance decomposition is a part-of-whole result and the
finding is almost always "one covariate dominates". A table makes the reader do
that comparison arithmetic; a bar shows it immediately. `make_stacked_bar`
returns `{type: "stacked_bar", segments: [{label, fraction, percent, color}]}`
and the UI dispatches on `type`, so a table and a bar travel through the same
`tables` field in the response.

Three details that matter:

- **Colours are fixed per component** (`VARIANCE_COLORS`), so Period is the same
  orange in every answer. Technical covariates are amber — they are the ones a
  reader should notice, because a large technical share means the signal may be
  tissue quality rather than biology.
- **Components under 1% merge into "Other"**, which carries the exact list in
  its tooltip. A 0.06% sliver is invisible in a bar and costs a legend entry for
  nothing. `test_agent.py` asserts every component appears either as a segment
  or inside Other, so nothing can silently vanish.
- **Segment order is drivers, then Other, then Residuals**, so the bar reads
  left-to-right as explained → minor → unexplained.

A footnote reports the technical total, and says "under 0.1%" rather than
"0.0%" when it rounds to zero.

Prompt rule 18a caps the accompanying prose at one or two sentences: the
dominant driver and the technical total. The legend already carries the rest,
and a paragraph beside the bar is worse than either alone — the reader has to
check whether the two agree.

### Tables

Tools that return tabular results include a `table` field, collected into the
response's `tables[]` and rendered by the client. The model is told to refer
to a table rather than retype its numbers, so what the user reads is what the
tool computed — the same reasoning behind computed superlatives below.

```jsonc
{"type":"table", "title":"SHANK3 — mean expression by age interval",
 "columns":[{"key":"age_interval","label":"Age Interval"},
            {"key":"mean","label":"Mean Expression","align":"right","format":"2dp"}],
 "rows":[["8-9pcw",2.103,30], ["10-12pcw",2.116,45]],
 "highlight_row":7, "highlight_note":"peak",
 "footnote":"log2(RPKM+1), 524 BrainSpan samples."}
```

`format` is `2dp`, `3dp`, `pct` or absent. `highlight_row` is an index into
`rows` — used for the peak marker. Cell values are HTML-escaped client-side.

### Asking what is in the dataset

`describe_metadata` answers "what is actually in BrainSpan" — every variable
with its range or category counts, and how many samples have a value. Pass a
`variable` name (display form such as `PMI (hours)` or internal `PMI`) to
profile just one.

Completeness is the reason this tool exists rather than a static blurb. In
BrainSpan, RIN, PMI, dissection score, hemisphere and ethnicity are recorded
for 367 of 524 samples, and pH for only 303. Any covariate analysis silently
runs on that subset, so the agent is instructed to state the denominator
whenever it reports on one of these.

### Superlatives are computed, not inferred

`get_developmental_trajectory` returns `steepest_transition` and
`transitions_by_magnitude`, and the system prompt forbids deriving a
"steepest"/"highest"/"fastest" claim by reading the series.

This is not hypothetical. While building the mockup for this feature, a
caption asserting the steepest rise in SHANK3 fell between 25–38 pcw and
0–5 months was wrong: the real largest step is 19–24 pcw to 25–38 pcw
(+1.089 vs +0.663 log2 units). The list of means was right there and the
claim was still wrong. Any question shaped "where does it change most"
must be answered from a computed field.

---

## How this integrates with the BITHub site

### How the site reads its data today

There is no server. `svelte.config.js` uses `adapter-static`, `+layout.js`
sets `ssr = false`, and CI uploads `frontend/build` as static files. The data
path is:

1. `+layout.svelte` resolves a `source` — `?source=` if present, otherwise the
   CloudFront `metadata.json` — and `createCore()` fetches it for the dataset
   list.
2. It downloads an HDF5 index with **jsfive** from `<source dir>/out.hdf5` and
   reads a root attribute named `remote`: triples of `[hdf5 group, index path,
   record type]`.
3. Each gene row lives in `expression.bin` as an independently zlib-compressed
   protobuf record. `pipeline/main.py:write_compressed_ranges` records the
   `(start, end)` byte offsets of each row while writing.
4. To draw a gene, the browser issues an HTTP **Range** request for exactly
   those bytes against CloudFront, inflates with **pako**, and decodes with
   the generated protobuf in `src/gen/data_pb.js`.

So the site is a static bundle doing random access into a large binary blob
over Range requests — no query engine, no API. This is why the chat needs a
separate service: it must hold an API key and run Python, and neither is
possible in that architecture.

### Pointing the chat at the same data — `BITHUB_SOURCE`

Steps 1 and 2 are the contract the chat has to match, because a chat answering
from a different bundle than the plot beside it is worse than no chat. The
backend therefore resolves its data the same way (`chatbot/source.py`): take
the metadata URL, strip the filename, read `out.hdf5` and `expression.bin` as
siblings of that directory.

Unset, `BITHUB_SOURCE` defaults to the literal in `+layout.svelte`, so a chat
started with no configuration reads exactly what a public visitor reads. Set
it, and the whole backend moves with it:

```bash
# the live site's data — the normal way to run this, nothing to set
.venv/bin/uvicorn main:app --port 8000

# a staging distribution, before it goes live
BITHUB_SOURCE=https://dXXXX.cloudfront.net/bithub/metadata.json ...

# a bundle already on disk: no server, no download, read in place.
# NOT the published data — the backend warns at startup.
BITHUB_SOURCE=../pipeline/output .venv/bin/uvicorn main:app --port 8000
```

`BITHUB_SOURCE` accepts a `metadata.json` URL, the directory holding one, a
`file://` URL, or a plain path. A local bundle is read directly off disk — the
loader mounts a `file://` adapter that honours Range, so the same
`_range_decode` path runs and no static server is needed. A remote bundle is
downloaded once into `chatbot/cache/`, under a name keyed to the source URL:
every bundle is called `out.hdf5`, so a fixed cache name would silently serve
the previous source's copy after a switch.

To reproduce what the site shows for a given visitor, pass their `?source=`
value as `BITHUB_SOURCE` — the two then cannot disagree.

**These are different bundles, and they differ.** The `pipeline/output` copy on
this machine is not the one CloudFront serves. Checked directly: HDBR regions
read `Choroid plexus` from CloudFront and `Chroid plexus` locally, so a chat
pointed at the local bundle will surface a misspelling the live site does not
have. Confirm which bundle you mean before drawing conclusions from region
names or sample counts. A local source prints a warning at startup and is
reported by `/api/health`; the `/ask` header flags it when the two halves of
the app disagree.

**`BITHUB_LOCAL_DATA=1` is a separate, older path** — the BrainSpan CSV/parquet
files under `chatbot/data/`, not a bundle at all. That directory is absent from
this deployment, so the flag fails with a message naming the missing files. It
is kept for the standalone development checkout that still has them.

### The in-app route

`/ask` is a normal SvelteKit route that calls the FastAPI service over HTTP:

```
frontend/src/routes/ask/+page.svelte     the page
frontend/src/lib/stores/chat.js          module-level chat state
frontend/src/lib/components/chatmessage.svelte
frontend/src/lib/components/chattable.svelte
frontend/src/lib/components/chatfigure.svelte
frontend/src/lib/utils/downloadicons.js  shared mode-bar icon paths
```

Chat state is module-level rather than a `setContext` factory like
`createCore`: the conversation should survive navigation, so a user can ask
about a gene, open it in the gene view, and come back to the thread.

`chatfigure.svelte` renders Plotly directly instead of reusing
`plot.svelte` — that component takes a `plotlyArgs` store and needs the
`displaySettings` context from the gene-view layout, plus palette controls
that do not belong in a chat reply.

### Taking the answer away

Three things were added so a reply can leave the browser, because a figure a
researcher cannot cite is not much use.

**Per-figure downloads.** `chatfigure.svelte` carries the site's three
mode-bar buttons — `.svg`, `.png`, `.csv` — using the *same* icon paths and
the same `getFilenameFromHeading` helper as `plot.svelte`, so a chat export
is named like a gene-view export. The icons were extracted from
`plot.svelte` into `utils/downloadicons.js` rather than copied, so the two
components cannot drift apart. The mode bar is revealed on hover/focus only:
always-on controls over every figure in a scrolling transcript compete with
the prose, and hiding them entirely means nobody finds the downloads.

The CSV is derived from the **Plotly traces themselves**, in long format
(`series, x, y`), so what the reader sees is exactly what they get — no
second payload to fall out of sync, and no per-figure-type branch. Pie traces
carry `labels`/`values` instead of `x`/`y`; both are handled.

**Statistical caveats render with the figure.** When a figure spec carries
`statistical_note.warnings`, the note's `text` is drawn in a bordered strip
directly beneath the plot. The model is also told to state it in prose, but a
screenshot of the figure alone should not lose it.

**Whole-conversation JSON export.** The Export button in the `/ask` header
calls `exportChat()` in `stores/chat.js`, which serialises every turn with
what the backend actually returned — `tables`, `figures` (full Plotly specs),
`literature`, `tools_used`, `datasets_used`, `datasets_unavailable`,
`elapsed_ms` — plus the dataset selection and `data_source` at export time.
Prose alone would not be reproducible: the point of the file is that a
reviewer can see which datasets and which tools produced each claim. Empty
fields are omitted so the file stays readable. Entirely client-side; the
backend holds no session state.

The backend URL comes from `VITE_CHAT_API` via `src/lib/config.js` — plain
`import.meta.env`, because both SvelteKit env modules are wrong here (see
"How the frontend finds the backend" above).

The home-page entry point is behind `{#if dev}`, so `/ask` compiles into the
production bundle (`build/ask.html`) but nothing links to it until you decide
to deploy the backend. Verified: `npm run build` succeeds, `svelte-check`
reports 0 errors, and the card does not appear in `build/`.

### To make it public

1. Deploy `chatbot/` somewhere with the key in the environment.
2. Set `BITHUB_ALLOWED_ORIGINS` to the CloudFront origin.
3. Build the frontend with `VITE_CHAT_API=https://your-api VITE_SHOW_CHAT=true`.
4. Add rate limiting first — see the deployment checklist below.
5. The entry point appears automatically once `VITE_SHOW_CHAT=true`; no code change needed.

---

## Units — the discrepancy that matters

BrainSpan is **RPKM**, not TPM. An earlier version of this service said TPM
throughout — in the system prompt, every tool payload and the UI. It is now
RPKM everywhere; `test_agent.py` asserts the unit string so it cannot drift
back silently.

This service reports **log2(RPKM+1)**. The BITHub gene view reports **z-scored**
values from the packing pipeline. Same gene, same data, different numbers on
screen at the same time.

Both the system prompt and the chat page state the unit. If the chat is ever
embedded next to a gene-view plot, resolve this properly — either serve
z-scores alongside, or label both axes explicitly.

Note `pipeline/input.yaml` still lists BrainSpan matrices under `name: TPM`.
That is test-fixture config outside this service, but it is the same
mislabelling and worth correcting at the source.

---

## Multiple datasets

The UI is a multi-select: each dataset is a chip, several can be active at
once, and the selection rides along on every `/api/chat` request. Selecting
two or more is how a user asks "does this hold up in another cohort".

Only BrainSpan has files on disk today, so the other seven render disabled.
The machinery around them is real, not a placeholder — `DatasetRegistry` in
`data_loader.py` holds the loaded datasets, resolves a requested selection,
and answers cross-dataset queries. **Adding a second dataset is one loader
instance plus one line in `main.py`:**

```python
registry = DatasetRegistry({
    "BrainSpan": loader,
    "BrainSeq":  brainseq_loader,      # tools, API and UI already handle it
})
```

### Units make this harder than it looks

BITHub's eight datasets do not share a unit:

| Unit | Datasets |
|---|---|
| RPKM | BrainSpan, BrainSeq, HDBR |
| TPM | GTEx, PsychENCODE |
| CPM | Cameron, HCA, Velmeshev |

A log2(RPKM+1) value and a log2(CPM+1) value are different quantities, so
comparing raw expression between datasets is meaningless. `compare_datasets`
therefore reports a **z-score**: mean log2 expression standardised across
genes within each dataset — reproducing exactly what `pipeline/main.py`
writes to `metadata/<dataset>/zscores/All` and the gene view plots as
"Z-Score Transformed Mean Log2 (Expression)".

The offset matters. The pipeline uses `log2(|v| + 0.05)`, not `log2(v + 1)`:
47.7% of the BrainSpan matrix is exactly zero, and those entries map to
-4.32 rather than 0, which moves the mean and SD of the whole distribution.
An earlier version of this loader used +1 and put ACTB at z = +5.56 where the
site shows +3.60 — the chat would have contradicted the plot beside it.
`PIPELINE_LOG2_OFFSET` in `data_loader.py` must track `LOG2_OFFSET` in
`pipeline/main.py`; `test_agent.py` reads the pipeline source and fails if
they diverge.

Each row carries both, with `native_unit` naming the underlying scale, and
`scale_note` tells the model that only `zscore` is comparable. Sanity check
on BrainSpan: ACTB +3.60, GAPDH +3.37, GFAP +2.48, SHANK3 +1.66, FOXP2 +0.58
— the housekeeping genes sit at the top, as they should.

### Guards against false corroboration

The failure mode worth engineering against is an answer that says "this
replicates across datasets" when only one was actually queried.

- `compare_expression` returns `comparison_possible: false` plus an explicit
  `warning` when fewer than two datasets return data.
- Requested-but-unloaded datasets come back in `unavailable` with a reason —
  never silently dropped. The UI renders them in an amber banner.
- The system prompt states the current selection on every turn, and rule 9
  forbids the words "corroborated" or "replicates" unless two or more
  datasets returned rows. Rule 10 requires reporting disagreement rather than
  averaging it away.
- A request naming only unloaded datasets returns HTTP 400 rather than
  quietly answering from whatever happens to be loaded.

The agent is also told, per rule 7, never to answer from a different dataset
than the one asked about.

---

## Differential expression — not implemented, and a note on how to

Benchmarked on this machine over the full 52,376 x 524 matrix:

| Step | Time |
|---|---|
| Load parquet + log2 | 0.26 s |
| Welch t-test, all genes, vectorised (`scipy.stats.ttest_ind`) | **0.1 s** |
| Benjamini-Hochberg FDR | <0.01 s |

Prenatal vs postnatal gives 31,304 genes at q<0.05, of which 4,178 also
exceed |log2FC| > 1 across 50,660 testable genes.

**On demand is fast enough** for simple two-group contrasts — the model call
dominates the turn, not the statistics. Precomputing the obvious contrasts
(period, plus the three region pairs) would be about 2.4 MB of float32, so
storage is not the deciding factor either.

The real reason to precompute is not speed but **method**. A Welch t-test
ignores the nested structure the variancePartition results already show
matters here: DonorID accounts for 11% of variance in SHANK3, and donors
contribute multiple regions. A defensible analysis needs a mixed model or
`limma`/`dream` with a donor random effect, which is minutes rather than
milliseconds and belongs in the R pipeline beside the existing varPart step.

Suggested split, if you go ahead:

- **Precompute** the canonical contrasts properly in `data-preprocessing/`
  with donor as a random effect, and ship the result as a parquet the chat
  reads — same pattern as `BrainSpan_varPart.csv`.
- **On demand** only for ad-hoc subsets a user invents mid-conversation, and
  label the output as an exploratory unadjusted screen, not a result.

The trap to avoid is a fast on-demand t-test that *looks* authoritative in a
chat window. A researcher will paste those numbers into a manuscript.

---

## Configuration

| Variable | Default | Purpose |
|---|---|---|
| `ANTHROPIC_API_KEY` | *(required)* | Startup fails without it |
| `BITHUB_CHAT_MODEL` | `claude-sonnet-4-6` | Model id |
| `BITHUB_SOURCE` | the site's CloudFront `metadata.json` | Which bundle to read. A `metadata.json` URL, the directory holding one, or a local path; `out.hdf5` and `expression.bin` are taken as its siblings |
| `BITHUB_DATA_DIR` | `chatbot/data` | Data location (local mode only) |
| `BITHUB_LOCAL_DATA` | unset | `1` forces the local CSV/parquet (BrainSpan only) instead of the published bundle |
| `BITHUB_REMOTE_DATA` | unset | Legacy opt-in, now redundant — the bundle is the default |
| `BITHUB_CACHE_DIR` | `chatbot/cache` | Where the downloaded `out.hdf5` is cached (one entry per source) |
| `BITHUB_REMOTE_DATASETS` | all eight | Comma-separated subset to load in remote mode |
| `BITHUB_ALLOWED_ORIGINS` | localhost 5173/8000 | Comma-separated CORS list |
| `BITHUB_MAX_TOOL_ROUNDS` | `10` | Tool-loop ceiling per question |

`.env` is gitignored. Never commit a key.

---

## Deployment

Not done yet, and deliberately so. Before this goes anywhere public:

1. **Rate limit.** An open endpoint spends your Anthropic credits for anyone
   who finds it. Per-IP and per-day ceilings, enforced server-side.
2. **Tighten CORS.** Set `BITHUB_ALLOWED_ORIGINS` to the real site origin.
   The wildcard the prototype started with is not acceptable in production.
3. **Ungate the link.** Remove the `{#if dev}` guard in
   `frontend/src/routes/+page.svelte` and point `CHAT_URL` at the deployed
   service.
4. **Watch memory.** The loader holds the full matrix in RAM — roughly 110 MB
   as float32, so a 512 MB instance is the practical floor.
5. **Consider streaming.** A multi-step tool loop can take 10–20 seconds. The
   current design POSTs and waits; SSE would need changes on both sides.

The BITHub frontend is a static `adapter-static` build with `ssr = false`, so
it cannot host this itself — a SvelteKit `+server.js` endpoint will not run.
The service must be deployed separately whatever the target.

---

## Deploying

`../DEPLOYMENT.md` covers GitHub Pages for the frontend — short version: the
gene explorer works there, the chat cannot, because Pages has no server.

`HOSTING.md` covers free hosts for this backend, with the measured memory
footprint that decides which tiers can run it — 454 MB with all eight datasets,
244 MB with three (peak under load, not just at startup).

## Layout

```
chatbot/
├── main.py                  FastAPI app, routes, CORS, startup checks
├── agent.py                 Tool definitions, system prompt, agent loop
├── data_loader.py           BrainSpanLoader — column mapping, queries, figures
├── chat.html                Standalone chat page
├── scripts/build_parquet.py CSV -> parquet
├── requirements.txt
├── .env.example
└── data/                    (gitignored)
```

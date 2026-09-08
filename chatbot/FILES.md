# What each file in `chatbot/` is for

Classification derived from the import graph, `deploy/Dockerfile`, and
`.dockerignore` — not from filenames. Verified against the deployed service at
`ecqhnavk6e.ap-southeast-2.awsapprunner.com`.

The runtime graph is small:

    main.py ──> agent.py ──> data_loader.py
            ├─> remote_loader.py ──> data_loader.py, source.py
            └─> source.py
                              (remote_loader also imports pipeline/data_pb2.py)

Production runs the **remote bundle** path. `main.py` computes
`USE_REMOTE = _remote_flag or not _local_flag`, so with `BITHUB_LOCAL_DATA`
unset — which is the deployed state — the local CSV/parquet branch is never
entered and the 150 MB expression matrix need not exist.

## Required at runtime

| File | Role |
|---|---|
| `main.py` | FastAPI app: `/health`, `/api/chat`, `/chat`, `/standalone`, `/`. Chooses the loader. |
| `agent.py` | Tool-use loop against the Anthropic API. `MAX_TOOL_ROUNDS = 10`. |
| `data_loader.py` | Dataset loaders and every analysis tool the agent calls. Largest file (120 KB). |
| `remote_loader.py` | Reads the published bundle over HTTP. The production data path. |
| `source.py` | Resolves where the bundle lives, using the frontend's sibling-of-metadata rule. |
| `../pipeline/data_pb2.py` | Protobuf messages for the bundle's binary rows. Imported by bare name; the Dockerfile copies it separately. |
| `requirements.txt` | Dev dependency list. Production uses `deploy/requirements-prod.txt`. |
| `.env.example` | Config template. The real `.env` is gitignored and never enters the image. |

`cache/out-<digest>.hdf5` (14 MB) is the downloaded bundle index. Gitignored but
**copied by the Dockerfile**, so a fresh clone cannot build the image until it is
populated. `deploy/deploy-chat.sh` fails with a clear message when it is absent,
so this is a prerequisite rather than a silent break. The digest in the filename
keys the cache to the source URL — a fixed name would serve a stale index after
the source changes.

## Needed, but not at runtime

| File | Role |
|---|---|
| `chat.html` | Self-contained chat page, no frontend build required. **Do not delete:** `/standalone` reads it at request time, and `/` falls back to it when no frontend build is mounted — which is the production case. Removing it makes both routes return HTTP 500. |
| `test/*.py` (7 files, 55 KB) | Test suite. Imports `agent`, `main`, `data_loader`, `remote_loader`, `source`. |
| `aws-policies/*.json` (6 files) | IAM policies for the deploy. `bithub_passrole_inline.json` is the one that works — attach it inline, unversioned. |
| `README.md` (57 KB) | Documentation. Excluded from the image by `**/*.md`. |
| `scripts/build_parquet.py` | Converts the BrainSpan CSV to parquet. Only matters on the local path: `data_loader.py:574` prefers a sibling `.parquet` and otherwise warns "csv (slow — run scripts/build_parquet.py)". |

## Redundant

| File | Why |
|---|---|
| `check_key.py` | 13-line scratch script that sends "Say hello" to verify the API key. `/health` covers this. Already excluded from the image. |
| `this_script.py` | Prints headers of files in `chatbot/data/` — a directory that **does not exist** in this checkout. Dead unless you restore the local data layout. Already excluded from the image. |
| `generate_gene_annotation.py` | One-shot generator for `gene_annotation.csv`. Its output is referenced only by `main.py:42` (local path) and `this_script.py`. Needs `mygene`, which is in neither requirements file. Keep only if you will rebuild the local dataset. |
| `.env.example.operon-tmp-8b23eea757f0` | Zero-byte editor temp file. Now gitignored. |
| `.DS_Store` | Finder metadata. |
| `__pycache__/`, `.venv/` | Build products. **`.venv` is 1.1 GB** — the single largest thing in the repo. Both excluded from git and the image. |

## Two dead rules in `.dockerignore`

Found while tracing this; neither is urgent, both are misleading.

1. **`chatbot/test_*.py` matches nothing.** Docker patterns are path-based and
   `test_*` cannot cross a `/`, so it does not match `chatbot/test/test_agent.py`.
   No file named `chatbot/test_*.py` exists — the tests were moved into `test/`.
   The suite therefore **ships in the image**. Harmless (55 KB, never imported by
   `main`), but the rule reads as though it were excluded. Fix: `chatbot/test/`.

2. **`aws-policies/` and `scripts/` ship too.** 32 KB of IAM JSON and a
   parquet builder in a production image. No secrets — these are policy
   documents, not credentials — so this is tidiness, not a security issue.

## What is safe to delete

`check_key.py`, `this_script.py`, the `.operon-tmp-*` file, and `.DS_Store` are
unreferenced by any runtime module. `generate_gene_annotation.py` is only
reachable if you rebuild the local dataset.

Do **not** delete `chat.html` (two live routes read it), `cache/` (the image
build copies it), or `source.py` (small, but `main.py` and `remote_loader.py`
both import it).

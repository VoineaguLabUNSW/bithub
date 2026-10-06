# Ownership and contributions

Who wrote what in the BITHub repository, and how to verify it.

Repository: <https://github.com/VoineaguLabUNSW/bithub>
Scope of this document: `origin/main` as of commit `0b58dfc` (2026-10-06),
106 commits spanning 2023-11-27 to 2026-10-06.

Every claim below is derived from git history and is reproducible with the
commands shown. Where a statement rests on something git cannot show — notably
the authorship of the chat feature — that is stated explicitly rather than
implied.

---

## Contributors

Commit counts are per committer identity, consolidated where one person has
used several git identities.

| Contributor | Commits | Active | Git author names in history |
|---|---|---|---|
| **Kieran Walsh** | 51 | 2023-11 → 2026-09 | `WalshKieran` (44), `Kieran Walsh` (7) |
| **Urwah Nawaz** | 49 | 2025-09 → 2026-10 | `urwahnawaz` (32 across three addresses), `Urwah Nawaz` (17) |
| **Vishal Uppal** | 6 | 2023-12 → 2026-09 | `Vishal Uppal` (6) |

Reproduce:

```bash
git shortlog -sn origin/main
```

Email addresses are deliberately omitted from this document. Commit history
necessarily records them, so `git shortlog -sne` (note the `-e`) will show the
addresses behind each name if you need to audit the consolidation; the counts
above are by name only.

Urwah Nawaz's commits are split across four git identities — three email
addresses at two institutions plus a GitHub web identity — all the same
person. A `.mailmap` would consolidate them in all future `git shortlog`
output, but writing one means committing those addresses to a tracked file,
which is the opposite of what this document does. Left unadded for that
reason.

---

## Ownership by component

| Component | Primary author | Evidence |
|---|---|---|
| `frontend/` (core site) | Kieran Walsh | 48 of 59 commits touching the path |
| `pipeline/` | Kieran Walsh | 16 of 17 commits |
| `proto/` | Kieran Walsh | sole author |
| `data-preprocessing/` | Urwah Nawaz | sole author, 20 commits |
| `chatbot/` | see [The chat feature](#the-chat-feature-ask-bithub) | 6 commits, all committed by Urwah Nawaz |
| `deploy/`, `demo.sh`, `share.sh` | Urwah Nawaz | sole author |
| `.github/workflows/` | shared | Kieran Walsh and Urwah Nawaz |

Reproduce for any path:

```bash
git log origin/main --format='%an' -- <path> | sort | uniq -c | sort -rn
```

### Kieran Walsh — web application and data pipeline

The original BITHub application and the machinery that feeds it. This is the
oldest and largest body of work in the repository, beginning at the first
commit in November 2023.

- **SvelteKit frontend**: gene search, result tables and graphs, the
  expression/variance/z-score views, transcript expression, the IGV genome
  panel, the dataset and help pages. Sole or near-sole author of
  `lib/stores/core.js`, `lib/utils/hdf5.js`, `lib/components/plot.svelte`,
  `lib/components/geneview.svelte`, `routes/search/+page.svelte`.
- **Packing pipeline** (`pipeline/`): z-score transformation, gene filtering,
  and packing of expression and metadata into the HDF5 index plus
  range-addressable `expression.bin` that the browser reads.
- **Wire format** (`proto/`): the protobuf schema for binary expression rows.

The browser-side range-request data path — HDF5 index lookup, byte-range
fetch, inflate, protobuf decode — is his design. The chat backend's
`remote_loader.py` is a deliberate reimplementation of it in Python, so that
the chat and the site read the same bytes.

### Urwah Nawaz — data preprocessing, chat feature, deployment

- **Dataset preprocessing** (`data-preprocessing/`): sole author. Cleaning and
  harmonisation of the eight source datasets, metadata curation, anatomical
  region and developmental stage definitions, sample and feature QC,
  deconvolution results, and the variancePartition analyses. The R code,
  notebooks, and the metadata summary figures used in the manuscript.
- **Chat feature** (`chatbot/`, `frontend/src/routes/ask/`): specified,
  directed, reviewed and committed — see the next section for the division of
  labour with Claude.
- **Deployment** (`deploy/`, `demo.sh`, `share.sh`, `check-chat-gate.sh`):
  the App Runner deployment, Docker image, IAM policies, the ngrok sharing
  path with its access-key gate and rate limits, and the check that keeps the
  chat entry point out of the production static build.
- Repository documentation, including the root `README.md`.

### Vishal Uppal — frontend contributions

Six commits across 2023-12 to 2026-09: the screen-capture `.webm` walkthrough
videos, the datasets page, the search-page gradient, colour utilities
(`lib/utils/colors.js`), modal label and ordering fixes, and the default scale
setting. Also merged the transcript-heatmap branch.

---

## The chat feature (Ask BITHub)

The conversational interface was **written by Claude** (Anthropic), working
under the direction of Urwah Nawaz, who specified the requirements, supplied
the domain knowledge, reviewed the output, and committed it.

`chatbot/CLAUDE.md` is the authoritative record for this component and
describes the division of labour in detail. A summary follows.

### What this covers

Introduced in two commits on 2026-09-04, together adding ~10,300 lines:

| Commit | Subject | Added |
|---|---|---|
| `505b0ac` | code for chatbot | 29 files, 8,856 lines |
| `28f91b7` | Ask BITHub: chat backend on App Runner, frontend entry point | 17 files, 1,464 lines |

Backend (`chatbot/`):

| File | Lines | Role |
|---|---|---|
| `data_loader.py` | 2,657 | Dataset loaders and every analysis tool the agent calls |
| `agent.py` | 944 | Tool-use loop against the Anthropic API |
| `remote_loader.py` | 783 | Reads the published bundle over HTTP — the production data path |
| `main.py` | 498 | FastAPI app, loader selection, auth and rate limiting |
| `source.py` | 151 | Resolves where the bundle lives |
| `test/*.py` | 1,154 | Seven-file test suite |
| `README.md`, `FILES.md` | — | Component documentation |

Frontend (`frontend/src/`):

| File | Lines |
|---|---|
| `routes/ask/+page.svelte` | 253 |
| `lib/stores/chat.js` | 217 |
| `lib/components/chatfigure.svelte` | 119 |
| `lib/components/chatmessage.svelte` | 110 |
| `lib/components/chatbar.svelte` | 67 |
| `lib/components/chattable.svelte` | 61 |
| `lib/utils/markdown.js` + test | 172 |
| `lib/config.js` | 39 |

### How this attribution is recorded — and its limits

**Git history does not record Claude's involvement.** Both commits are
authored and committed by Urwah Nawaz, and neither carries a
`Co-authored-by:` trailer. Verify:

```bash
git log origin/main --format='%b' -- chatbot | grep -i co-authored-by   # no output
git log --all -i --grep=claude                                          # no output
```

The attribution in this document and in `chatbot/CLAUDE.md` therefore rests on
the record of the repository owner who directed and committed the work, not on
metadata inside the commits. That is a deliberate distinction: rewriting the
two published commits to add trailers would change their hashes and break any
existing clone or reference, so the history is left intact and the attribution
is documented alongside it.

For future work, `Co-authored-by:` trailers are the durable mechanism and
render on each commit in the GitHub UI:

```
Co-authored-by: Claude <noreply@anthropic.com>
```

### Not to be confused with the runtime model

`chatbot/agent.py` sets a model id for the service to **call at run time**:

```python
MODEL = os.environ.get("BITHUB_CHAT_MODEL", "claude-sonnet-4-6")
```

This is the model the deployed chat queries to answer user questions. It is a
dependency of the running service, not evidence about who wrote the code. The
two facts are independent: the authorship claim above would stand even if the
service were repointed at a different provider.

---

## Third-party code

The repository depends on, but does not vendor, work by others. Notable
runtime dependencies of the chat feature, added in `28f91b7`:
`marked` and `dompurify` (markdown rendering and sanitisation in
`lib/utils/markdown.js`), `jsdom` and `linkedom` (test-time DOM). The site
itself uses `svelte`, `flowbite-svelte`, `igv`, `jsfive`, `chroma-js` and
others; see `frontend/package.json`. The chat backend's Python dependencies
are in `chatbot/requirements.txt` and `deploy/requirements-prod.txt`.

Source datasets are the work of their originating consortia — BrainSpan,
BrainSeq, HDBR, GTEx, PsychENCODE, Cameron, HCA and Velmeshev — and are
redistributed here in harmonised form. See the root `README.md` and the
manuscript for dataset citations. Authorship of the code that processes a
dataset does not imply ownership of the dataset.

---

## Verifying any claim in this document

```bash
# Contributors, by author name
git shortlog -sn origin/main

# Who has touched a given path
git log origin/main --format='%an' -- frontend/ | sort | uniq -c | sort -rn

# Line-level authorship of a specific file
git blame --line-porcelain origin/main -- chatbot/agent.py \
  | grep '^author ' | sort | uniq -c | sort -rn

# What a commit changed
git show --stat 505b0ac
```

Note that `git blame` attributes lines to the committer who introduced them.
For `chatbot/`, that is Urwah Nawaz for every line; see the section above for
why, and `chatbot/CLAUDE.md` for the actual division of labour.

---

## Maintaining this document

Update it when a component changes hands, a contributor joins, or a new
component is added. The commit counts and the `0b58dfc` reference in the
header will drift as history grows — re-run the commands in the previous
section rather than editing the numbers by hand.

*Last updated: 2026-10-06, against `origin/main` at `0b58dfc`.*

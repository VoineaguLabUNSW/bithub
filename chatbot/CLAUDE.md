# CLAUDE.md — authorship and working notes for `chatbot/`

This file serves two purposes:

1. **Attribution** — a record that the Ask BITHub chat feature was written by
   Claude (Anthropic) under the direction of Urwah Nawaz.
2. **Working notes** — context for any future Claude session asked to modify
   this component, which is the conventional use of a `CLAUDE.md`.

Repository-wide contribution records are in [`../OWNERSHIP.md`](../OWNERSHIP.md).

---

## Attribution

The Ask BITHub conversational interface — the FastAPI backend in this
directory and the chat UI under `frontend/src/` — was **written by Claude**,
Anthropic's AI assistant, working interactively with and under the direction
of **Urwah Nawaz**.

### Division of labour

**Claude wrote:** the implementation. The tool-calling agent loop, the dataset
access and analysis layer, the HTTP bundle reader, the FastAPI service, the
test suite, the Svelte chat interface and its markdown sanitisation, and the
component documentation (`README.md`, `FILES.md`).

**Urwah Nawaz provided and owns:** the specification and scientific direction.
Which questions the interface must answer, the dataset semantics it has to
respect, the statistical caveats it must carry, what it must refuse to do, and
the judgement on whether each answer was correct. Also all review, testing
against real queries, and every commit.

The domain constraints encoded in this code did not originate with Claude and
could not have. They are decisions from the BITHub work: that absolute
expression values are not comparable across datasets because they are RPKM,
TPM or CPM depending on cohort; that nuclei are not donors, so n must not be
reported as a sample count for single-nucleus data; that variance
decomposition belongs in a bar chart rather than a table; that certain
questions should be refused rather than answered with a misleading number.
Claude implemented those rules. Urwah Nawaz knew they were the right rules.

> **Note for Urwah:** this division is written from your statement that Claude
> wrote the chatbot, plus what is evident in the code. If the split differs —
> if you wrote or substantially rewrote particular files, or if the
> specification was looser or tighter than described — edit this section
> before merging. It should be accurate rather than generous in either
> direction.

### Scope

| Area | Path |
|---|---|
| Chat backend | `chatbot/` — `agent.py`, `data_loader.py`, `remote_loader.py`, `main.py`, `source.py`, `test/` |
| Chat frontend | `frontend/src/routes/ask/`, `frontend/src/lib/stores/chat.js`, `frontend/src/lib/components/chat*.svelte`, `frontend/src/lib/utils/markdown.js`, `frontend/src/lib/config.js` |
| Documentation | `chatbot/README.md`, `chatbot/FILES.md`, this file |

Introduced on 2026-09-04 in commits `505b0ac` (29 files, 8,856 lines) and
`28f91b7` (17 files, 1,464 lines).

**Not covered by this attribution.** The deployment — `deploy/`, the IAM
policies in `aws-policies/`, `demo.sh`, `share.sh`, `check-chat-gate.sh` — and
the data this service reads, which comes from the pipeline and preprocessing
work described in `../OWNERSHIP.md`.

### What git history does and does not show

Both commits are authored and committed by Urwah Nawaz. Neither carries a
`Co-authored-by:` trailer, and no commit message in the repository mentions
Claude:

```bash
git log origin/main --format='%b' -- chatbot | grep -i co-authored-by   # no output
```

So `git blame` will attribute every line here to Urwah Nawaz. That is a
property of how the work was committed, not a contradiction of this file.
This document is the record; the history was left unrewritten because
amending published commits would change their hashes.

For future commits to this component, add the trailer so the attribution lives
in the history as well as in this file:

```
Co-authored-by: Claude <noreply@anthropic.com>
```

### The runtime model is a separate matter

`agent.py` sets `MODEL = os.environ.get("BITHUB_CHAT_MODEL", "claude-sonnet-4-6")`.
That is the model the **deployed service calls** to answer user questions — a
runtime dependency, configurable via environment variable. It is not evidence
about authorship, and the two should not be cited as if they were the same
fact. If the service were repointed at another provider tomorrow, the
authorship record above would be unchanged.

### Citing this

If the chat feature is described in a paper or presentation, the honest
formulation is that the interface was implemented with Claude (Anthropic)
under author direction. Check the target venue's policy on AI-assisted
contributions — most now ask for disclosure in the methods or
acknowledgements, and none accept an AI system as a named author.

---

## Working notes for future sessions

Read `FILES.md` first: it classifies every file in this directory by whether
it is needed at runtime, and was derived from the import graph rather than
from filenames. `README.md` is long but is the real documentation.

Things that are easy to get wrong here:

- **Production reads the remote bundle, not local files.** `main.py` computes
  `USE_REMOTE = _remote_flag or not _local_flag`, so with `BITHUB_LOCAL_DATA`
  unset — the deployed state — the local CSV/parquet branch never runs. Test
  changes on the path that actually ships.
- **`remote_loader.py` must stay byte-compatible with the frontend.** It is the
  Python equivalent of `frontend/src/lib/stores/core.js`: HDF5 index lookup,
  byte-range fetch, inflate, protobuf decode. The point is that a number in a
  chat answer cannot disagree with the plot beside it. Changing one side
  without the other breaks that guarantee silently.
- **Column names are normalised once at load time.** The R pipeline exports
  display-formatted headers (`"Age (Numeric)"`, backtick-quoted
  variancePartition names). Add a dataset by extending the maps at the top of
  `data_loader.py`, not by renaming at the call site.
- **Every per-gene tool declares `dataset`.** `dispatch_tool` routes on
  `args["dataset"]`; a tool that omits the parameter silently gets
  `selection[0]` while the system prompt tells the model to name a dataset.
- **Units differ by dataset** — RPKM (BrainSpan, BrainSeq, HDBR), TPM (GTEx,
  PsychENCODE), CPM (Cameron, HCA, Velmeshev). Cross-dataset comparison goes
  through `compare_datasets`, never two single-dataset calls.
- **`chat.html` is load-bearing.** `/standalone` reads it at request time and
  `/` falls back to it when no frontend build is mounted — the production
  case. Deleting it makes both routes return HTTP 500.
- **The service holds an API key.** CORS is a browser policy and does not
  protect `/api/chat`; an exposed endpoint spends Anthropic credits for whoever
  finds it. The access-token gate and rate limits exist for that reason — do
  not remove them to simplify a test.
- **The chat entry point is gated out of the production static build**
  (`lib/config.js`, `check-chat-gate.sh`). Keep it that way unless the backend
  is deployed and rate-limited.

Known limitation recorded in the source: `remote_loader.py` describes itself
as a working prototype exercised against a synthetic bundle, not verified
against the live CloudFront bundle at the time of writing. Check whether that
is still true before relying on it.

---

*Maintained by Urwah Nawaz. Last updated 2026-10-06.*

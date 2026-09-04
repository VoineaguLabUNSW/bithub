# Free hosting for the Ask BITHub backend

The frontend goes on GitHub Pages (see `../DEPLOYMENT.md`). This is about the
FastAPI service, which needs a host that runs Python.

Free tiers change often and several listed here have tightened recently — check
the provider's own pricing page before committing, and treat the numbers below
as of July 2026.

---

## What you actually need to fit

Measured on this machine, remote mode (`BITHUB_REMOTE_DATA=1`), after startup:

| Datasets loaded | After startup | Under load |
|---|---:|---:|
| Python + pandas + numpy + h5py + fastapi (imports only) | 128 MB | — |
| 1 (BrainSpan) | 203 MB | 208 MB |
| 3 (BrainSpan, BrainSeq, HDBR) | 228 MB | 244 MB |
| **8 (all)** | **454 MB** | **454 MB** |

Up from 180 / 217 / 438 MB: the genomic annotation table added for
`find_genes_in_locus` and `gene_info` costs ~20 MB, held once per bundle. It
was briefly ~45 MB worse than that — each of the eight loaders built its own
copy of a table that is a property of the *bundle*, not the dataset, taking
all-eight to 499 MB and past the usable headroom on a 512 MB tier. It is now
memoised per HDF5 file (`_bundle_annotation`), so eight loaders share one
table.

"Under load" is peak resident memory after exercising `compare_datasets`,
`describe_metadata`, `get_developmental_trajectory` and a box figure in one
process — the number a hosting tier actually has to accommodate. Startup alone
understates it by 8–15 MB. Figures vary by 1–2 MB between runs; size a tier with
headroom rather than treating them as exact.

Each extra dataset costs roughly 37 MB — its sample-metadata frame and z-score
series, held for aggregate queries. Expression rows are fetched per gene and
LRU-cached, so they are not the driver.

**This is the number that decides your options.** On a 512 MB tier, 454 MB
leaves almost nothing for request handling; `BITHUB_REMOTE_DATASETS` is the lever:

```bash
BITHUB_REMOTE_DATASETS=BrainSpan,BrainSeq,HDBR   # 244 MB under load, comfortable
```

Verified with that setting: 228 MB after startup, 244 MB after exercising the
tools; three datasets load, `compare_datasets` returns three rows with
`comparison_possible: true`, and a question about an unloaded dataset is refused
by name ("Dataset 'GTEx' is not loaded. Available: …") rather than answered from
one of the three. Trimming costs coverage, not correctness.

Other requirements: **~1 GB disk** for the dependency tree (pandas, numpy,
h5py, pyarrow, tooluniverse), **outbound HTTPS** to CloudFront and the Anthropic
API, and **~15 MB writable disk** for the cached bundle index — re-downloaded on
each cold start if storage is not persistent, which is fine.

## UPDATE (30 Aug 2026) — you will have an AWS account, which changes this

This document was written before the CDN migration. Once you own the AWS
account that serves BITHub's data, **host the chat there too.** Two reasons that
did not apply before:

1. **The $200 signup credits cover it outright.** A Lightsail 2 GB instance is
   in the region of $10-12/month, so the credits run well over a year. Nothing
   below is cheaper once credits are counted, and no free tier avoids sleeping.
   **Check the current figure on AWS's own Lightsail pricing page** — the number
   here comes from third-party 2026 writeups, not from AWS, and Lightsail plan
   prices have been revised before.
2. **Same-region reads are free.** Put the instance in the same region as the
   bucket (`ap-southeast-2`) and S3→instance traffic is not billed as internet
   egress. The chat's data reads then cost nothing, whereas an off-AWS host pays
   CloudFront egress for every range request.

Sizing: **2 GB, not 1 GB.** The measured all-8-datasets figure below is 438 MB
under load, and a 1 GB instance leaves too little for the OS plus the ~1 GB
dependency tree unpacking during install. 2 GB runs all eight datasets with no
`BITHUB_REMOTE_DATASETS` trimming, which is the whole point of remote mode.

One region caveat to check at signup: Asia-Pacific regions including Sydney
appear to carry a **smaller included data-transfer allowance** than us-east-1
for the same plan price. I could not confirm the exact figures against AWS's own
page, so treat this as a prompt to look rather than a number to trust. It is
almost certainly irrelevant at BITHub's traffic — the chat returns JSON to
browsers, not the 15 MB index — but confirm before assuming a published
allowance applies to `ap-southeast-2`.

Not Lambda or any serverless option: a chat turn runs a multi-step tool loop
taking 10-20 s, and the 128 MB import cost is paid on every cold start.

---

## Two things that will break a deploy — fix before hosting anywhere

Both are code, not configuration. Neither shows up until startup on the host.

### 1. Reading a file from a sibling directory — FIXED

The backend used to get the bundle's URLs from the frontend's repo copy of
`metadata.json`, reached by relative path:

```python
site_meta = json.loads(
    (Path(__file__).parent.parent / "frontend" / "static" / "metadata.json").read_text())
```

Deploying `chatbot/` alone raised `FileNotFoundError` at startup, before
serving a request — and commit 062f92e deleted that file outright, so it now
fails in the repo too. It was also a silent-staleness bug when the file *was*
present: a copy pointing at an old distribution would keep the chat reading
the lab's old bucket while the website read yours.

Both are resolved. `chatbot/source.py` derives `out.hdf5` and `expression.bin`
as siblings of a single metadata URL, which is the rule the frontend itself
adopted in 062f92e:

```bash
BITHUB_SOURCE=https://<your-distribution>/bithub/metadata.json
```

Unset, it defaults to the same literal `+layout.svelte` uses, so the chat and
the site read one bundle by construction. Set it on the host to your own
distribution and the whole backend moves with it — nothing else to change, and
no repo file is read at startup.

### 2. `remote_loader.py` hardcodes the old CDN

`https://d33ldq8s2ek4w8.cloudfront.net/bithub/metadata.json` appears in the
module docstring's usage example and in an error message. Harmless today,
misleading after migration — but no longer load-bearing: the one value that
matters is `source.DEFAULT_SOURCE`, and `BITHUB_SOURCE` overrides it without
touching code. Update `DEFAULT_SOURCE` when you cut over, to keep the
zero-configuration default honest.

### And check which bundle you are pointing at

`update_2/bithub/pipeline/output/metadata.json` points at
`http://localhost:5501` — it is the local `deploy_local` build's output. Those
URL fields are now ignored on both sides, so it no longer breaks anything; but
the bundle *beside* it is a different pipeline run from the published one.
Checked directly: HDBR regions read `Choroid plexus` on CloudFront and
`Chroid plexus` in that local copy. Pointing `BITHUB_SOURCE` at a local
directory is supported and needs no static server, but be deliberate about it —
`/api/health` reports the resolved source, so check there if an answer looks
unfamiliar.

---

## Options (pre-AWS; still valid if you host off-AWS)

**Render — free web service.** The closest fit to a plain `uvicorn` deployment:
connect the repo, set the start command, add environment variables. The free
instance **sleeps after inactivity** and cold-starting takes tens of seconds, on
top of this service's own ~2.4 s startup and the 15 MB index download. Memory on
the free tier is 512 MB, so run a trimmed dataset list.

**Railway.** Similar deployment model. Its free allowance is trial credit rather
than a perpetual tier, so it suits a time-boxed demo more than a service you
leave up. Check the current dashboard — this is the one most likely to have
changed since writing.

**Hugging Face Spaces (Docker SDK).** Technically the best fit for a research
tool — 2 vCPU and 16 GB RAM, well past what this needs, with built-in secrets
management. **But note a conflict in the sources:** HF's own Spaces
documentation now states that Gradio and Docker Spaces require a paid plan
(PRO, $9/month) and that only Static Spaces are free for everyone, while several
2026 third-party guides still describe Docker Spaces as free on CPU Basic. The
official docs are the ones to trust; verify on the pricing page before relying
on it. If it does need PRO, $9/month for 16 GB is still the best value here, and
HF grants free hardware to some research demos on request.

**A small VPS (Hetzner, ~€4/month).** Not free, but no sleep, no memory ceiling
to work around, and it removes the cold-start problem entirely. Worth naming
because for a supervisor-facing demo that must work on the first click, €4 buys
more reliability than any free tier.

### Two that will not work

**PythonAnywhere free tier — no ASGI support.** FastAPI does not run there at
all on the free plan, regardless of memory. Its outbound HTTP is also restricted
to an allowlist, which would block both CloudFront and the Anthropic API.

**Fly.io** withdrew its free trial, so it is no longer a free option.

Anything serverless (Lambda, Cloud Functions, Vercel functions) is a poor fit
for a different reason: a chat turn runs a multi-step tool loop that can take
10–20 s, and the 128 MB of import overhead is paid on every cold invocation.

## Before you deploy anywhere

Non-negotiable, because the endpoint spends your Anthropic credits:

```bash
BITHUB_ACCESS_TOKEN=<generated>       # share.sh shows the pattern
BITHUB_RATE_PER_IP_HOUR=20
BITHUB_RATE_TOTAL_DAY=200
BITHUB_ALLOWED_ORIGINS=https://<you>.github.io
BITHUB_REMOTE_DATA=1                  # bundle, not the 245 MB local data
BITHUB_REMOTE_DATASETS=BrainSpan,BrainSeq,HDBR
ANTHROPIC_API_KEY=<key>               # as a platform secret, never committed
```

CORS is browser-enforced and does nothing against `curl`, so the token and the
rate limits are the actual protection. Rate limiting is in-memory: it resets on
restart and does not span replicas, which is adequate for one free instance and
not for anything larger.

The backend must be HTTPS — an https Pages site calling an http API is blocked
as mixed content.

## Or skip deployment

`./share.sh` puts `demo.sh` behind an ngrok tunnel with a generated access
token: a public HTTPS URL, no signup, nothing left running afterwards. For
showing one person the chat, it is less work than any option above.

# Publishing a data bundle to CloudFront

Ordered checklist for pushing `pipeline/output/` to the live site. Every claim
here was verified against this checkout on 17 Aug 2026 — line numbers refer to
`pipeline/main.py` in this repo.

**Read the two STOP gates before you start.** The upload writes directly to the
bucket the public site reads, and there is no rollback.

---

## The one-paragraph version

> **Read `REPACK-ON-OTHER-MACHINE.md` first.** The source matrices exist on
> another machine, so a full repack is possible and is the better route. This
> checklist is the fallback for publishing from *this* laptop with what is
> already built.

There is no upload command. Uploading is what `pipeline/main.py` does when
`deploy_local` is false. Because the expression matrices are **not on this
machine**, a full repack is impossible *here*, so the only route available on
this laptop is `deploy_only: True` — which uploads what is already in `output/`
and exits.
That path has a defect: it uploads `metadata.json` verbatim, and yours
currently contains `localhost` URLs. Fix that file *before* uploading or you
will break the chat for everyone.

---

## STOP gate 1 — this overwrites production, permanently

The bucket is hardcoded as `'bithub-bucket'` at `main.py:45` and `main.py:49`.
`deploy_bucket` in the YAML is **never read** — grep confirms zero references.
So `deploy_local: False` means "write to production" regardless of config.

- Same bucket, same `bithub/` prefix, same distribution the public site reads.
- No S3 versioning in `pipeline/deployment/main.tf`.
- **No rollback.** The previous bundle is gone once overwritten.

## STOP gate 2 — your data is not the live data

This is not a re-upload of identical bytes. Publishing changes the numbers for
every visitor:

| | live (CloudFront) | yours (`pipeline/output/`) |
|---|---|---|
| `last_updated` | January 2026 | August 2026 |
| HCA samples | 46,958 | 47,194 |
| Velmeshev samples | 81,215 | 81,216 |
| `out.hdf5` | 15,292,929 B | 15,081,554 B |

The HCA difference is a known open question — `input_allData.yaml:105` carries
the comment that the live build used the `-subset` file (46,958) rather than
`HCA-metadata.csv` (47,194). **Resolve which is correct before publishing.**
If the subset was deliberate, publishing silently changes the cohort.

---

## Prerequisites

None of this tooling is installed on this machine as of 17 Aug 2026 — no
`aws`, no `terraform`, no `conda`, no `boto3`.

```bash
conda env create -f pipeline/environment.yml   # creates bithub-env
conda activate bithub-env
```

`environment.yml` pins `python<3.12` and includes `terraform`, `awscli`,
`boto3`, `h5py`, `oyaml`, `protobuf`, `tqdm`, `numpy`, `scipy`.

Then authenticate:

```bash
aws sso login --profile <profile>
export AWS_PROFILE=<profile>
aws sts get-caller-identity     # must succeed before you go further
```

---

## Step 1 — verify locally first

Do this every time. It is the only safety net.

Serve the bundle and click through the site. Range requests are mandatory —
`frontend/src/lib/stores/core.js` streams gene rows out of the 3.3 GB
`expression.bin` by byte range and hard-fails on any non-206 response
(`'Invalid response, 206 expected'`), so `python -m http.server` will not do.

Two servers work:

```bash
# stdlib only, mounts the /pipeline/output/ prefix, run from repo root
python3 tools/serve_pipeline.py

# or the pre-existing one — needs `pip install rangehttpserver`,
# and must ALSO run from the repo root, not from pipeline/
python pipeline/serve.py
```

Both must run from the **repo root**. `manage_deploy_local` (`main.py:26`)
builds URLs relative to `'../'`, producing
`http://localhost:5501/pipeline/output/...`. The RUNBOOK's instruction to run
from `pipeline/` is wrong for this layout.

Point the frontend at it:

```bash
cp pipeline/output/metadata.json frontend/static/metadata.json
cd frontend && npm run build
```

Check in the browser: gene search, expression plots, the developmental
trajectory view. **If anything is wrong, stop — do not publish.**

---

## Step 2 — fix `metadata.json` before uploading

This step does not exist in the RUNBOOK and is the easiest way to break the
live chat.

`deploy_only: True` (`main.py:602-604`) does:

```python
deploy([os.path.join(OUTPUT_FOLDER, p) for p in os.listdir(OUTPUT_FOLDER)])
exit(0)
```

It uploads **everything** in `output/` — including `metadata.json` — and exits
at line 604, *before* the code at line 921 that would regenerate that file with
CloudFront URLs. So the localhost version goes to the CDN verbatim.

That matters because `chatbot/main.py:194` builds its loader from
`site_meta["bin_url"]`, read from the published `metadata.json`. A localhost
`bin_url` on the CDN means `remote_loader.py` raises `RemoteBundleError` and
the chat stops working for everyone.

Edit `pipeline/output/metadata.json` and replace both URL fields:

```json
"data_url": "https://d33ldq8s2ek4w8.cloudfront.net/bithub/out.hdf5",
"bin_url":  "https://d33ldq8s2ek4w8.cloudfront.net/bithub/expression.bin"
```

Any `meta_url` entries per dataset need the same treatment. Verify no
`localhost` remains:

```bash
grep -c localhost pipeline/output/metadata.json    # must print 0
```

### About the path baked inside `out.hdf5`

`out.hdf5` carries an embedded `path` attribute on each matrix. In your build
it reads `http://localhost:5501/pipeline/output/expression.bin`. **Leave it.**

The live bundle has the same defect from an older run —
`http://localhost:5501\..\output-final-feb\expression.bin`, with Windows
backslashes — and the site works anyway, because both consumers take the URL
from `metadata.json` instead: `core.js:97` reads `$metadata.value.bin_url`, and
`remote_loader.py` rejects any embedded localhost value and requires an
explicit override. Fixing the attribute would require a full repack, which is
not possible here.

---

## Step 3 — upload

```yaml
# in pipeline/input_allData.yaml
deploy_local: False
deploy_only: True
deploy_url: "d33ldq8s2ek4w8.cloudfront.net"
```

```bash
cd pipeline
python main.py input_allData.yaml
```

Use `input_allData.yaml` — it is the config that produced the current output
(edited 10:16, output written 10:18-10:49).

Expect the full **3.3 GB** of `expression.bin` over the wire. ETag comparison
(`main.py:44-47`) skips unchanged files, but this one changed. Uploads use
multipart with `Cache-Control: max-age=3600`.

### Why not a full repack *on this machine*

`deploy_only: False` would repack from source and write correct URLs
everywhere, including inside `out.hdf5`. It is not available **here**: the
per-dataset expression matrices (`BrainSeq-exp.csv`, `HCA-exp.csv`, …) are
absent from `data-preprocessing/output/*`, which holds only metadata,
annotation, deconvolution and variance-partition files. Nothing over 100 MB
exists on disk apart from `expression.bin` itself.

**CORRECTED (30 Aug 2026):** the matrices are not lost — they live on another
machine, which also has more disk and cores. A full repack *is* available
there, and it is the better route: it eliminates the January/August vintage
mismatch instead of documenting it. See `REPACK-ON-OTHER-MACHINE.md`. Treat the
hand-edit route below as the fallback for when you must publish from this
laptop.

Note that in a normal (non-`deploy_only`) run the order matters:
`expression.bin` uploads alone at `main.py:849`, its URL is written into
`out.hdf5` and `metadata.json`, then everything else uploads at `main.py:918`.
`deploy_only` bypasses this and uploads in `os.listdir` order — safe only
because you fixed `metadata.json` by hand in step 2.

---

## Step 4 — invalidate the cache

Nothing in the codebase calls `create_invalidation`. With `max-age=3600`,
CloudFront can serve the old bytes for an hour, edge caches possibly longer.

This is the dangerous failure mode: a **stale `expression.bin` paired with a
fresh `out.hdf5`** means byte offsets point at the wrong rows. The site shows
plausible numbers for the wrong genes rather than failing loudly.

```bash
aws cloudfront create-invalidation --distribution-id <id> --paths '/bithub/*'
```

The distribution ID is not in this repo — `deployment/main.tf` outputs
`cloudfront_url` (the domain, line 108-111) but not the ID, and there is no
committed `.tfstate`. Get it from the AWS console, or:

```bash
aws cloudfront list-distributions \
  --query "DistributionList.Items[?DomainName=='d33ldq8s2ek4w8.cloudfront.net'].Id" \
  --output text
```

---

## Step 5 — point the site at the new bundle

`metadata.json` belongs to the frontend, not the bundle. Per the RUNBOOK,
forgetting this is the classic way to leave the site on the previous data.

```bash
cp pipeline/output/metadata.json frontend/static/metadata.json
cd frontend && npm run build
git add frontend/static/metadata.json && git commit -m "Point site at August bundle"
```

Since you edited that file in step 2, it now carries CloudFront URLs — which
also resolves the working-tree diff that currently points the site at
`localhost:5501`.

---

## Step 6 — clear the chat's cache

`chatbot/cache/out.hdf5` is a local copy of the published index (currently from
16 Aug). If it survives the deploy, the chat reads the **old index against the
new binary** — the same silent offset mismatch as step 4.

```bash
rm ~/Documents/Projects/BITHub_2.0/bithub/chatbot/cache/out.hdf5
```

It re-downloads on next start.

---

## Step 7 — verify what is actually live

```bash
# vintage should now read August 2026
curl -s https://d33ldq8s2ek4w8.cloudfront.net/bithub/metadata.json \
  | python3 -c "import json,sys; m=json.load(sys.stdin); \
      print(m['last_updated'], m['bin_url']); \
      print([(d['name'], d['samples']) for d in m['meta_files']])"

# range requests must still work — expect HTTP 206
curl -sI -H 'Range: bytes=0-1023' \
  https://d33ldq8s2ek4w8.cloudfront.net/bithub/expression.bin | head -3
```

Then check a gene end to end. Pick one with a known value — before publishing,
`SHANK3` on the live bundle read z=1.277 / mean log2=3.479 in BrainSpan
(n=524). After publishing, the same query should return your August numbers.
If it still returns the January ones, the cache has not cleared.

Finally, open the site and the `/ask` page and confirm both agree on the same
gene. Disagreement means one of them is still on the old bundle.

---

## Rollback

There isn't one. No S3 versioning, no retained copy of the January bundle.

The only recovery is to rebuild the previous bundle from its source data and
re-upload — which needs the expression matrices that are not currently on this
machine. **Treat step 1 as mandatory, not advisory.**

# Upload the new build and point the live site at it

You are running `main.py` on the Linux machine and you have an AWS account.
This is everything from "the run finishes" to "bithub.org shows the new data".

**Do not set `deploy_local: False` to upload.** `main.py:45` and `:49` hardcode
`Bucket='bithub-bucket'` — the lab's bucket. `deploy_bucket` in the yaml is
**never read** by `main.py` (grep confirms zero references). With your own
credentials that fails with AccessDenied *after* the multi-hour build; with lab
credentials it would overwrite production. Keep `deploy_local: True` and upload
with the AWS CLI, which takes the bucket as an argument.

---

## The one thing to understand first

There are **two** separate `metadata.json` files and confusing them is the main
way this goes wrong.

| file | who reads it | what it must contain |
|---|---|---|
| `pipeline/output/metadata.json` | nobody in production | pipeline output; has localhost URLs |
| `frontend/static/metadata.json` | **the live website** | CloudFront URLs; must be **committed to git** |

`+layout.svelte:10` fetches `${base}/metadata.json` — from the **site's own
origin**, not from CloudFront. So the site finds your data only when the
*frontend's* copy is updated and pushed. Uploading to S3 alone changes nothing
the site can see.

### The full URL chain — nothing about the data location is hardcoded

Worth walking once, because `core.js:97` looks like it should be the place you
edit and it is not:

```
svelte.config.js       base = process.env.BASE_PATH  ──► "/bithub" at build time
  └─ +layout.svelte:10   url = `${base}/metadata.json`   (SAME ORIGIN, baked in)
       └─ createCore(url)                                 core.js:37
            └─ getJSON(url)                               core.js:27-30  runtime fetch
                 └─ metadata store                        core.js:41-47
                      ├─ $metadata.value.data_url  ──►  getHDF5()   core.js:54
                      └─ $metadata.value.bin_url   ──►  fetch()     core.js:97
```

`core.js:97` reads `$metadata.value.bin_url` — a **runtime value from the JSON**.
`createCore` takes the URL as a parameter (`core.js:37`), and `getJSON` is a
plain `fetch` of whatever it is handed. Change the JSON, change where the data
comes from. No rebuild of the JS is needed for the URLs themselves.

The **only** thing baked into the bundle is the path to `metadata.json`, and it
is same-origin — `/bithub/metadata.json`, served out of `frontend/static/` by
adapter-static. That is why the file must be committed rather than merely
uploaded to S3.

A grep across `frontend/src` finds exactly one hardcoded data URL, and it is not
in this chain: `genome.svelte:20-21`, the FCAT genome tracks. Those are the
genuine hardcoded exception and step 6 fixes them.

Practical consequence: because `metadata.json` is fetched at runtime rather than
inlined, **the browser caches it**. After pushing, verify in a private window or
the old URLs persist and it looks like the deploy failed.

---

## Step 1 — while the run is going: create the AWS infrastructure

On the **laptop**, where the terraform lives.

```bash
brew install awscli terraform

# IAM console -> Users -> Create user -> attach AmazonS3FullAccess
# and CloudFrontFullAccess -> Security credentials -> Create access key (CLI)
aws configure --profile bithub-personal
#   region: ap-southeast-2      output: json

aws sts get-caller-identity --profile bithub-personal   # must NOT be 790772245098
```

Fill the two placeholders in `pipeline/deployment/main.tf`:

```hcl
profile = "bithub-personal"                  # line 17
bucket  = "bithub-data-<something-unique>"   # line 24 — globally unique across all AWS
```

```bash
cd pipeline/deployment
grep -n CHANGEME main.tf     # must print nothing
terraform init
terraform plan               # expect 8 to add, 0 to change, 0 to destroy
                             # (bucket, versioning, lifecycle, public-access-block,
                             #  policy, CORS, OAI, distribution)
terraform apply              # 10-20 min, blocks on distribution deployment
```

**Record the `cloudfront_url` it prints** — `dXXXXXXXXXXXXX.cloudfront.net`.
Everything below needs it. Also back up `terraform.tfstate` somewhere off this
machine; it is gitignored (`pipeline/.gitignore:1`).

---

## Step 2 — when the run finishes: check it before uploading anything

On the **Linux machine**.

```bash
cd pipeline
wc -l output/errors.tsv          # expect only a header line
ls -la output/
```

You should see ~21 files, ~11.3 GB, including `expression.bin` (~3.5 GB),
`out.hdf5` (~15 MB), 8 `*_*.csv.gz` matrices and 8 `*-metadata.csv`.

Then confirm the datasets and the HCA fix landed:

```bash
python3 -c "
import json; d=json.load(open('output/metadata.json'))
print('datasets:', len(d['meta_files']), '| genes:', d['count'])
for e in d['meta_files']: print(' ', e['name'], e['samples'])
"
```

Expect **8 datasets, 34440 genes**, and HCA at **47194** samples (the January
publish had 46958 — the difference is the metadata fix). If HCA still reads
46958, the run used the old subset file; stop and check the yaml.

---

## Step 3 — upload to S3

Still on the Linux machine. Install the CLI and configure the **same** profile:

```bash
# Ubuntu/Debian
curl "https://awscli.amazonaws.com/awscli-exe-linux-x86_64.zip" -o awscliv2.zip
unzip -q awscliv2.zip && sudo ./aws/install

aws configure --profile bithub-personal    # same key, region ap-southeast-2
```

> If this machine is **shared with other people**, do not put your main access
> key here. Create a second IAM user limited to `s3:PutObject` on your bucket,
> use that key, and delete it after the upload.

```bash
export AWS_PROFILE=bithub-personal
B=s3://bithub-data-<something-unique>/bithub

cd pipeline/output
aws s3 cp . $B/ --recursive \
  --cache-control max-age=3600 \
  --exclude "metadata.json" \
  --exclude "errors.tsv" \
  --exclude "warnings.log" \
  --exclude ".DS_Store" \
  --exclude "*.new"
```

The `bithub/` prefix is **not optional** — it is baked into the URL layout
(`main.py:manage_deploy_cloudfront` uses `prefix='bithub'`).

Excluding `metadata.json` is deliberate: the pipeline's copy has localhost URLs
and nothing in production reads it from S3 anyway.

Verify — expect 19 objects:

```bash
aws s3 ls $B/ --human-readable --summarize
```

---

## Step 4 — upload the two genome-browser tracks from the LAPTOP

These are **not pipeline output**. `FCAT_lv3_liftover_sorted.gtf.gz` (55 MB) and
its `.tbi` exist only in the laptop's mirror — a fresh clone does not have them
and the run does not produce them.

```bash
# on the laptop
export AWS_PROFILE=bithub-personal
B=s3://bithub-data-<something-unique>/bithub
cd ~/Documents/Papers/BITHub/Website/update_2/cdn-backup-2026-08
aws s3 cp . $B/ --recursive --exclude "*" --include "FCAT_*" \
  --cache-control max-age=3600
```

Now `aws s3 ls $B/` should show **21 objects**.

---

## Step 5 — rewrite metadata.json for CloudFront

`pipeline/repoint_metadata.py` converts the localhost URLs. Run it wherever the
new `output/metadata.json` is (Linux machine, or copy that one 4 KB file to the
laptop first — easier).

```bash
cd pipeline
python3 repoint_metadata.py dXXXXXXXXXXXXX.cloudfront.net
```

It writes `output/metadata.json.new` and never overwrites in place. It converts
18 URLs, refuses to write if any `localhost` survives, and is idempotent.

Check the HCA metadata filename — this changed:

```bash
grep -o '"meta_url": "[^"]*HCA[^"]*"' output/metadata.json.new
```

Must end `HCA-metadata.csv`, **not** `HCA-metadata-subset.csv`. If your S3
upload has the other name, the download link 404s.

---

## Step 6 — put it in the frontend and push

On the **laptop**, in a clone of `VoineaguLabUNSW/bithub`.

```bash
cp pipeline/output/metadata.json.new frontend/static/metadata.json
git diff --stat frontend/static/metadata.json
```

The diff should show URLs moving from the old distribution
(`d33ldq8s2ek4w8.cloudfront.net`) to yours, `last_updated` becoming
`August 2026`, HCA samples `46958 -> 47194`, and the HCA meta filename change.

**Also fix the genome browser** — `frontend/src/lib/components/genome.svelte`
lines 20-21 hardcode the old distribution for the FCAT tracks. They are not in
`metadata.json`, so nothing else repoints them:

```bash
sed -i '' 's/d33ldq8s2ek4w8\.cloudfront\.net/dXXXXXXXXXXXXX.cloudfront.net/g' \
  frontend/src/lib/components/genome.svelte
grep -rn d33ldq8s2ek4w8 frontend/src frontend/static   # must print nothing
```

Then commit to **`main`** — `.github/workflows/deploy.yml` builds and publishes
to GitHub Pages on every push to `main`, and nothing else:

```bash
git add frontend/static/metadata.json frontend/src/lib/components/genome.svelte
git commit -m "point site at new CloudFront distribution; August 2026 data"
git push origin main
```

Watch the Actions tab. Build is a few minutes.

> **Scope note.** This is the *only* change that has to reach `main` for the
> data to go live. The chat interface work stays on `front-end-changes` — do
> not merge that branch to publish data.

---

## Step 7 — verify from a browser, not curl

```bash
curl -sI https://dXXXXXXXXXXXXX.cloudfront.net/bithub/out.hdf5 | head -3
curl -s -H "Range: bytes=0-99" \
  https://dXXXXXXXXXXXXX.cloudfront.net/bithub/expression.bin -o /dev/null -w '%{http_code}\n'
```

The second must print **206**, not 200. A 200 means range requests are not
working and every gene lookup would download 3.5 GB.

Then open the live site in a **private window** (the old metadata.json is
cached), pick a gene, and confirm a plot renders. Check the genome browser tab
too — that is the FCAT path, which the metadata does not cover.

---

## Step 8 — the chat backend, if it is deployed

It caches `out.hdf5` and will keep serving January data until cleared:

```bash
rm -rf chatbot/cache/out.hdf5
```

And it needs the new URLs. `chatbot/main.py:165` currently reads them from
`../frontend/static/metadata.json` by relative path — see
`chatbot/HOSTING.md` for the environment-variable fix that decouples it.

---

## For FUTURE updates — invalidate the cache

Not needed this time: a brand-new distribution has nothing cached. It matters
every time after.

`out.hdf5` stores byte offsets **into** `expression.bin`, and both are uploaded
to the same URLs with `max-age=3600`. CloudFront caches them independently, so
after a re-upload an edge can hold the new `out.hdf5` alongside a stale
`expression.bin` for up to an hour. The offsets then point at the wrong bytes.
`core.js:108` catches some of these as "Unexpected response length", and
`core.js:127` catches inflate/decode failures — so it surfaces as an error
rather than silently wrong numbers, but the site is broken until the TTL expires.

Always follow a re-upload with:

```bash
aws cloudfront create-invalidation \
  --distribution-id <your-distribution-id> \
  --paths "/bithub/*"
```

That is why the IAM user needs `cloudfront:CreateInvalidation`. The first 1,000
invalidation paths per month are free.

---

## Rollback

The old distribution is untouched and still serving. To revert, restore the
previous `frontend/static/metadata.json` and push:

```bash
git revert <commit>
git push origin main
```

Your bucket has versioning enabled, so a bad upload can be rolled back
object-by-object too.

# BITHub data hosting — ownership and access

**Status: TEMPLATE. Fill in as you create the account, then commit.**

This document exists because it did not exist for the previous hosting account.
When the lab member who created that account left, nobody remaining could
write to the bucket, and there was no record of the account ID, the root
email, or who to ask. Recovering that cost far more effort than writing this
page would have.

If you are reading this because you inherited BITHub: everything you need
should be below. If something is missing, add it.

---

## Current hosting account

| Field | Value |
|---|---|
| AWS account ID | `_____________` (`aws sts get-caller-identity`) |
| Account alias | `_____________` |
| Root email | `_____________` |
| Who can read that mailbox | `_____________` |
| Root MFA device | `_____________` |
| Root credentials stored in | `_____________` (shared password manager, not personal) |
| Billing method | `_____________` |
| Billing contact | `_____________` |
| Monthly cost (approx) | `_____________` |
| Region | `ap-southeast-2` |

### Deploy credentials

| Field | Value |
|---|---|
| IAM user | `bithub-deploy` |
| Local AWS profile name | `bithub-personal` |
| Permissions | `s3:PutObject`, `s3:GetObject`, `s3:ListBucket` on the data bucket; `cloudfront:CreateInvalidation` |
| Access key rotated on | `_____________` |

Access keys should be rotated when anyone with a copy leaves.

### Resources

| Field | Value |
|---|---|
| S3 bucket | `_____________` |
| CloudFront distribution ID | `_____________` |
| CloudFront domain | `_____________` |
| S3 versioning | `_____________` (enabled = a bad upload is recoverable) |
| Terraform state | `pipeline/deployment/terraform.tfstate` — gitignored via `pipeline/.gitignore:1`, backup stored at `_____________` |

Losing the terraform state does not lose the resources, but it does mean
future changes must be made by hand or the state re-imported.

---

## Predecessor account (for reference)

| Field | Value |
|---|---|
| AWS account ID | `790772245098` |
| Registered to | a former lab member, under a personal identity |
| Access | none available to the current team |
| CloudFront domain | `d33ldq8s2ek4w8.cloudfront.net` |
| Status | `_____________` (still serving / retired on ____) |

**A complete read-only mirror was taken on 28 Aug 2026, before migration.**

| | |
|---|---|
| Location | `Website/update_2/cdn-backup-2026-08/` |
| Objects | 21 of 21, zero failures |
| Size | 11.29 GB (11,287,350,782 bytes) |
| Verification | all 21 byte-count exact against `manifest.json`; ETag confirmed on `*.gtf.gz.tbi` |
| Source | `d33ldq8s2ek4w8.cloudfront.net/bithub`, `last_updated: January 2026` |

18 of the 21 objects existed nowhere else — not in this repo, not in
`data-preprocessing/output/`. **Do not delete this mirror** until the new
distribution is live, verified, and independently backed up. It is currently
the only complete copy of BITHub's January 2026 published state outside an
account nobody can access.

The mirror is deliberately outside the git repo (11 GB). `mirror.py` alongside
it is resumable and can re-verify at any time.

---

## What is published, and what can be regenerated

| Object group | Count | Regenerable? |
|---|---|---|
| `expression.bin`, `out.hdf5`, `metadata.json` | 3 | Yes — `pipeline/main.py` from `data-preprocessing/output/` |
| `HCA-metadata.csv` | 1 | Yes — present in `data-preprocessing/output/HCA/` |
| Other per-dataset `*-metadata.csv` + matrices | 15 | **No** — source expression matrices are not in the repo |
| `FCAT_lv3_liftover_sorted.gtf.gz` + `.tbi` | 2 | **No** — origin unrecorded, dated Aug 2024 |

The 17 non-regenerable objects are the reason the mirror matters. If you are
planning any change to hosting, mirror first.

### Known inconsistency

As of the 2026 migration, the browsable expression data is the August 2026
build while 15 per-dataset download files are January 2026. If the August
build changed sample composition, downloads will not match plots. Resolve by
locating the source matrices and running a full repack.

---

## Where the code points at hosting

Changing hosting means editing all of these. Miss one and part of the site
silently keeps loading from the old distribution:

| File | What |
|---|---|
| `pipeline/input.yaml` → `deploy_url` | distribution domain |
| `pipeline/main.py` (~lines 45, 49) | bucket name, **hardcoded** |
| `pipeline/deployment/main.tf` | region, profile, bucket |
| `frontend/static/metadata.json` | committed URLs the site reads at load |
| `frontend/src/lib/components/genome.svelte` (~lines 20-21) | genome-browser tracks, **hardcoded**, not in metadata |
| `chatbot/` — reads URLs from the frontend metadata | no separate change needed |

Note `deploy_bucket` in `input.yaml` is **not read by any code**. Setting it
alone does nothing; the bucket is a string literal in `main.py`.

---

## Procedures

- `PUBLISH-CHECKLIST.md` — publishing a new build to existing hosting
- `PUBLISH-TO-OWN-AWS.md` — standing up hosting in a different account
- `pipeline/RUNBOOK.md` — running the pipeline

---

## Handover log

| Date | From | To | Notes |
|---|---|---|---|
| | | | |

Append a row whenever ownership or access changes.

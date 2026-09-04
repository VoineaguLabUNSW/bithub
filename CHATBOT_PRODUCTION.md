# Putting Ask BITHub on the live site

Your instinct is right: **GitHub Pages cannot host the chat.** Pages serves
static files only, and a chat turn runs a multi-step tool loop in Python
holding an Anthropic API key. There is no process to run it in, and a key
shipped in a static bundle is a published key.

So the deployment splits in two:

```
  GitHub Pages                          A small server you run
  ─────────────                         ──────────────────────
  bithub.org (static site)   ─────►     chat.bithub.org (FastAPI)
  built by .github/workflows            /api/chat, /api/health
  VITE_CHAT_API points here             holds ANTHROPIC_API_KEY
                                                │
                                                ▼
                                        CloudFront bundle
                                        (both halves read this)
```

The site stays exactly where it is. Only the chat moves.

---

## What you need to do

### 1. Stand up the API host

**Do not wait for the CDN migration, and do not put the chat in someone
else's AWS account.** Host it wherever you control — the two are independent.
See "Hosting the chat and the data in different places" below for the
measurements behind that.

`chatbot/HOSTING.md` covers the options. Any small always-on VM works: a
2 GB instance on Lightsail, Hetzner, Fly, DigitalOcean, or a university VM.
Pick the one you can keep credentials for.

Sizing is 2 GB, not 1 GB: all eight datasets measured 438 MB under load, and
the dependency tree needs room to unpack during install.

Not Lambda or any serverless option — a chat turn takes 10-20 s and pays the
import cost on every cold start. That is the same reason Pages cannot do it.

Set on that host:

```bash
ANTHROPIC_API_KEY=sk-ant-...
BITHUB_ALLOWED_ORIGINS=https://<your-pages-origin>
BITHUB_ACCESS_TOKEN=<a long random string>
BITHUB_RATE_PER_IP_HOUR=20
BITHUB_RATE_TOTAL_DAY=200
```

Leave `BITHUB_SOURCE` unset so it reads the published bundle — the same bytes
the site plots. Put HTTPS in front of it (Caddy or nginx + certbot); the
Pages site is HTTPS, so an HTTP API is blocked as mixed content.

### 2. Point the site at it

In `.github/workflows/deploy.yml`, add to the build step's `env:`

```yaml
          VITE_CHAT_API: https://chat.your-domain.org
          VITE_SHOW_CHAT: 'true'
```

Both are baked in at build time — this is a static site, so they cannot
change afterwards. `VITE_SHOW_CHAT` currently defaults to false, which is why
the chat entry point does not appear on the live site today.

### 3. Decide who can use it

`BITHUB_ACCESS_TOKEN` gates `/api/chat` only; browsing the site and reading
`/api/health` stay open. Two postures:

- **Public chat** — leave the token unset. Anyone can ask, rate caps are the
  only protection, and you are paying for every question. Only do this with
  billing alerts set.
- **Keyed** — set the token and share links as
  `https://<site>/ask?k=<token>`. The page stores the key for the tab and
  strips it from the address bar.

The rate caps are in-memory and per-process: they reset on restart and do not
coordinate across replicas. Adequate for one instance, not a substitute for
real infrastructure if this grows.

---

## Hosting the chat and the data in different places

**Yes, and you should.** The chat host and the data host are independent, and
coupling them to save egress does not survive the numbers.

### What the chat actually pulls

Measured against the live bundle, not estimated:

| | |
|---|---|
| Per gene query | **1.9 KB** (one HTTP range request) |
| 1,000 questions/month | 1.8 MB |
| 10,000 questions/month | 18 MB |
| Index download | 14.4 MB, once per instance, cached on disk after |

The chat is not a bulk data consumer. It seeks a few kilobytes out of a
3.5 GB `expression.bin` via range requests and returns JSON. `HOSTING.md`
argues for co-locating because "same-region reads are free" — at these
volumes that saves cents per month, which is not a reason to put the service
in an account you do not control.

### Why co-locating is actively worse here

The AWS account holding the current CDN belongs to someone else. That is the
exact situation `pipeline/deployment/OWNERSHIP.md` was written about: the
previous hosting account was registered to a lab member who left, and nobody
remaining could write to the bucket or recover the account. Putting the chat —
which holds a billable API key — into another account you do not control
repeats that mistake with an added liability.

Keep the chat somewhere you hold the credentials. Then the migration can
happen underneath it without touching the chat at all.

### Following the CDN when it moves

The chat reads its data location from one environment variable, so a new
distribution needs no code change and no redeploy of the site:

```bash
BITHUB_SOURCE=https://<new-distribution>/bithub/metadata.json
```

Verified: setting it re-derives both `out.hdf5` and `expression.bin` as
siblings of that URL. Restart the service, and the cache re-keys on the new
URL rather than serving the old bundle.

One thing to fix during the migration: `chatbot/source.py` line 44 holds its
own copy of the current CloudFront URL as `DEFAULT_SOURCE`, separate from the
frontend's default in `+layout.svelte`. It is only the fallback when nothing
is set, but it is a second place the old domain is written down, and
`OWNERSHIP.md` already warns that missing one such site leaves part of the
system silently loading from the old distribution. Add it to that document's
"Where the code points at hosting" table.

### Suggested order

1. **Now** — deploy the chat on infrastructure you control, pointed at the
   current CDN. It works today and is unaffected by the migration.
2. **Later** — run the CDN migration on its own schedule.
3. **After** — update `BITHUB_SOURCE` on the chat host and restart. One
   variable, one restart.

Doing the chat first also means the migration gets tested by something other
than the website: if the new distribution serves range requests incorrectly,
the chat surfaces it immediately.

---

## Two things I fixed while checking this

**CORS preflight would have failed on every chat request.** `X-BITHub-Token`
is not a CORS-safelisted header, so a cross-origin POST carrying it triggers
a preflight — and the header was missing from the allow-list. Same-origin
deployments (`demo.sh`, `share.sh`) never preflight, so nothing had caught
it. Verified after the fix: preflight from a Pages origin returns 200 with
`X-BITHub-Token` in `access-control-allow-headers`, and an unlisted origin
still gets no allow-origin header.

**A Pages-style build was untested.** Building with `BASE_PATH=/bithub` and a
cross-origin `VITE_CHAT_API` produces `ask.html`, bakes the absolute API URL
into the bundle, and resolves assets relatively so the base path holds. The
API host itself runs fine with no frontend build present — it reports
`frontend_mounted: false` and serves the standalone chat page at `/`.

---

## What I could not test

No live deployment. The sandbox cannot bind a port, so everything above was
verified against the app in-process rather than over a real network. The
first real deploy should check, in order:

1. `curl https://chat.your-domain.org/api/health` returns the CloudFront
   `source_url` and `source_is_local: false`
2. The browser console on the live `/ask` page shows no CORS error
3. One real question returns an answer with figures

If the chat says it cannot reach the backend, check `VITE_CHAT_API` was set
at **build** time — a missing value fails silently to same-origin, which on
Pages means requesting `/api/chat` from a static host: a 404, not an error
you would recognise as a config problem.

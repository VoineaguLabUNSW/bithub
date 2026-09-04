# Ask BITHub in `update_2/bithub` — running it

Everything is in place and tested. Two files hold secrets, so the sandbox that
did this work could not write them; create them and you are running.

## 1. The two files you need to create

**`chatbot/.env`** — the backend's API key:

```
ANTHROPIC_API_KEY=sk-ant-...
```

**`frontend/.env`** — build-time frontend config (copy `frontend/.env.example`):

```
VITE_CHAT_API=
VITE_SHOW_CHAT=true
```

`VITE_CHAT_API` empty means same-origin, which is right when one process
serves both the site and the API — the case below. `VITE_SHOW_CHAT=true`
reveals the "Ask BITHub" entry point on the home page in a production build.

**Keep `VITE_SHOW_CHAT=false` for the public GitHub Pages deploy.** That site
has no backend behind it; a visible chat entry point there is a dead link that
also advertises an endpoint spending Anthropic credits.

## 2. Run it

```bash
./demo.sh
```

Builds the frontend with the chat enabled and serves site + API from one
FastAPI process on `http://localhost:8000`. Site at `/`, chat at `/ask`.

First run downloads a 15 MB index into `chatbot/cache/`; afterwards it starts
immediately.

## 3. Sharing it with someone else

```bash
./share.sh
```

Builds the site, starts the backend, opens an ngrok tunnel, and prints a link
to send:

```
https://<random>.ngrok-free.app/ask?k=<key>
```

One prerequisite, once per machine — a free ngrok authtoken:

```bash
ngrok config add-authtoken <token>   # dashboard.ngrok.com/get-started/your-authtoken
```

### The link carries an access key, and that matters

`/api/chat` spends your Anthropic credits on every question. CORS does not
protect it — CORS is a browser rule and `curl` ignores it — and ngrok
subdomains are actively scanned, so the random URL is not a secret. Without a
key, whoever finds the URL is spending your money.

`share.sh` therefore generates a key and bakes it into the link. Your
recipient does nothing: the page reads `?k=`, stores it for the tab, and
strips it from the address bar. Pass `KEY=mysecret ./share.sh` to choose it.

Browsing the site needs no key — only asking questions does. Rate caps apply
on top: 20 questions/hour per visitor and 200/day overall, adjustable via
`BITHUB_RATE_PER_IP_HOUR` and `BITHUB_RATE_TOTAL_DAY`.

Ctrl-C closes the tunnel and stops the server. The key dies with it, so a new
`share.sh` means a new link — rotation by default.

> `demo.sh` stays open and un-keyed. It binds localhost only, so nothing
> outside your machine can reach it.

### If you get `502 Bad Gateway`

Look at the `Forwarding` line in ngrok's own output:

```
Forwarding  https://<random>.ngrok-free.dev -> http://localhost:80
                                                                ^^
```

A `502` means ngrok reached that port and found nothing listening. `80` is
what a bare `ngrok http` defaults to, and BITHub does not run there — so this
is the signature of starting ngrok by hand in a second terminal instead of
running `./share.sh`. The port after `localhost:` must match the backend's,
which is 8000 unless you set `PORT`.

Run `./share.sh` and it tunnels the same port it started the backend on, so
the two cannot disagree. It now also refuses to start if that port is already
occupied, naming the process.

Other things that produce a broken share link:

| Symptom | Cause |
|---|---|
| An ngrok warning page before the site | Free-plan interstitial. Expected; click through once |
| Site loads, chat says it cannot reach the backend | Site built with a `VITE_CHAT_API` pointing somewhere else. `./share.sh` sets it for you |
| `401` on every question | Link sent without the `?k=` part |

## 4. Which data it reads — the published bundle, same as the site

Both halves resolve data the same way: take a `metadata.json` URL, read
`out.hdf5` and `expression.bin` as siblings of it. Unset, both use the site's
CloudFront default, so **the chat answers from exactly what the page plots**.
This needs no configuration — it is what `./demo.sh` does.

```bash
./demo.sh              # the live site's published bundle — 8 datasets
PORT=8010 ./demo.sh    # different port
```

Verified on a clean start with an empty environment: `source_url` resolves to
the CloudFront `metadata.json`, `source_is_local` is `false`, all 8 datasets
load, and HDBR regions come back spelled `Choroid plexus`.

### Local data is not used, and is fenced off

`chatbot/data/` (the old BrainSpan CSV/parquet path) is absent from this
repo — `BITHUB_LOCAL_DATA=1` now fails with an explicit message naming the
missing files rather than half-starting.

`SOURCE=<url-or-path>` still overrides the bundle location, for testing a
staging distribution before it goes live. Be deliberate: `pipeline/output` on
this machine is a **different pipeline run** from the published one.

| Source | HDBR regions |
|---|---|
| CloudFront (default) | `Choroid plexus` |
| local `pipeline/output` | `Chroid plexus` |

The published bundle has the correct spelling, so the default needs no
pipeline run to be right. Three safeguards if a source is ever overridden:
the backend prints a startup warning naming the published URL, `/api/health`
reports the resolved `source_url`, and the `/ask` header compares it against
what the page loaded — showing **"same bundle as this page"** when they agree
and **"⚠ different bundle"** when they do not.

## 5. What changed in this repo

**New** — `chatbot/` (the backend, copied in), `chatbot/source.py`,
`demo.sh`, `frontend/src/lib/utils/downloadicons.js`, and the chat frontend
files (`chatbar`, `chatfigure`, `chatmessage`, `chattable`, `stores/chat.js`,
`config.js`, `utils/markdown.js`, `routes/ask/`).

**Modified** — `frontend/src/routes/+page.svelte` only: the chat entry point,
gated on `dev || SHOW_CHAT`, with `$page.url.search` threaded through so
`?source=` survives the hop.

No pipeline files, no data files, no existing site behaviour touched.

## 6. Verified

- 5 bundle test suites passing against the published source. `test_agent.py`
  skips by design: it covers the local CSV loader, and `chatbot/data/` is not
  part of this deployment
- All 17 agent tools dispatch and return real values against the live bundle
- All 8 datasets load; clean-start default resolves to CloudFront, not local
- Sharing: token gate returns 401 without a key and passes with it (header or
  `?k=`), while the site and read endpoints stay open; rate limiter returns
  429 exactly at the cap. The tunnel itself is untested — this sandbox cannot
  bind a port, so `share.sh` needs one real run on your machine
- `svelte-check`: 0 errors (15 warnings, all pre-existing unused CSS in one
  unrelated file)
- Site and API served from one process: `/`, `/ask`, `/search`, `/api/health`,
  `/api/datasets` all 200

Not verified here: a live model round-trip, which needs your API key. Ask it
something after `./demo.sh` — "How does SHANK3 expression change across brain
development?" exercises the whole path.

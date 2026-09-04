"""
BITHub chat backend.

Local development service. It is intentionally NOT hardened for public
deployment: CORS is restricted to localhost and there is no auth or rate
limiting, so do not expose this port to the internet — an open endpoint here
spends Anthropic credits for whoever finds it. See chatbot/README.md.

    uvicorn main:app --reload --port 8000
"""

import json
import os
import secrets
import time
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

load_dotenv(Path(__file__).parent / ".env")

from agent import MODEL, run_agent          # noqa: E402  (needs env loaded first)
from data_loader import (                   # noqa: E402
    BrainSpanLoader, DataFileMissing, DatasetRegistry,
)

# ── Data paths ────────────────────────────────────────────────────────────────
# Override with BITHUB_DATA_DIR when the files live outside the repo.

DATA_DIR = Path(os.environ.get("BITHUB_DATA_DIR", Path(__file__).parent / "data"))

EXPR_PATH       = DATA_DIR / "BrainSpan-exp.csv"          # .parquet used if present
META_PATH       = DATA_DIR / "BrainSpan-metadata.csv"
VP_PATH         = DATA_DIR / "BrainSpan_varPart.csv"
VP_DECON_PATH   = DATA_DIR / "BrainSpan_varPart_cellTypes.csv"
ANNOTATION_PATH = DATA_DIR / "gene_annotation.csv"

# Built SvelteKit site, served at / when present (see the mount at the bottom).
FRONTEND_BUILD = Path(os.environ.get(
    "BITHUB_FRONTEND_BUILD", Path(__file__).parent.parent / "frontend" / "build"
))

# ── Access control ────────────────────────────────────────────────────────────
#
# Only needed when the service is reachable from outside this machine (an
# ngrok tunnel, a deployed box). Locally it stays off so `demo.sh` needs no
# setup.
#
# CORS is NOT access control. It is enforced by browsers to stop one site
# reading another's responses; curl, a script, or any non-browser client
# ignores it entirely. An open /api/chat on a public URL spends real money
# for whoever finds it, and ngrok subdomains are actively scanned — a random
# URL is not a secret.

ACCESS_TOKEN = os.environ.get("BITHUB_ACCESS_TOKEN", "").strip()

# Per-IP and global caps. In-memory, so they reset when the process restarts
# and are per-replica — fine for a shared demo, not a substitute for real
# infrastructure on a permanent deployment.
RATE_PER_IP_HOUR = int(os.environ.get("BITHUB_RATE_PER_IP_HOUR", "20"))
RATE_TOTAL_DAY   = int(os.environ.get("BITHUB_RATE_TOTAL_DAY", "200"))

_ip_hits: dict[str, list[float]] = defaultdict(list)
_day_hits: list[float] = []


def check_access(request: Request) -> None:
    """
    Gate the one endpoint that costs money.

    Raises 401 when a token is configured and absent/wrong, 429 when either
    cap is hit. Read endpoints stay open so the site itself works for anyone
    with the link.
    """
    if ACCESS_TOKEN:
        supplied = (
            request.headers.get("X-BITHub-Token")
            or request.query_params.get("k")
            or ""
        )
        # compare_digest avoids leaking the token length/prefix via timing.
        if not secrets.compare_digest(supplied, ACCESS_TOKEN):
            raise HTTPException(
                status_code=401,
                detail="This BITHub chat needs an access key. Ask whoever shared the link.",
            )

    now = time.time()
    client = request.client.host if request.client else "unknown"

    _day_hits[:] = [t for t in _day_hits if now - t < 86_400]
    if len(_day_hits) >= RATE_TOTAL_DAY:
        raise HTTPException(
            status_code=429,
            detail=(
                f"Daily limit of {RATE_TOTAL_DAY} questions reached for this "
                "instance. It resets 24h after the first question."
            ),
        )

    hits = [t for t in _ip_hits[client] if now - t < 3_600]
    if len(hits) >= RATE_PER_IP_HOUR:
        _ip_hits[client] = hits
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit: {RATE_PER_IP_HOUR} questions per hour. Try again shortly.",
        )

    hits.append(now)
    _ip_hits[client] = hits
    _day_hits.append(now)


# ── App setup ─────────────────────────────────────────────────────────────────

app = FastAPI(
    title="BITHub Chat API",
    version="0.2.0",
    description="Conversational access to BrainSpan expression and variance data.",
)

# Local dev only. Vite serves on 5173; the standalone page is same-origin.
ALLOWED_ORIGINS = [
    o.strip() for o in os.environ.get(
        "BITHUB_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,"
        "http://localhost:8000,http://127.0.0.1:8000",
    ).split(",") if o.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_methods=["GET", "POST"],
    # X-BITHub-Token must be listed. It is not a CORS-safelisted header, so a
    # cross-origin POST carrying it triggers a preflight, and the browser
    # rejects the request outright if the header is not in the response's
    # allow-list. Same-origin deployments (demo.sh, share.sh) never preflight
    # and so never noticed; a split deployment — static site on GitHub Pages,
    # API on its own host — fails on every keyed chat request without this.
    allow_headers=["Content-Type", "X-BITHub-Token"],
)

# ── Data source ───────────────────────────────────────────────────────────────
#
# DEFAULT: BITHub's published bundle, read over HTTP Range requests — the same
# out.hdf5 index and expression.bin the website's own store (frontend/src/lib/
# stores/core.js) reads. The chat and the site therefore resolve every number
# from identical bytes, so a chat answer cannot disagree with the chart beside
# it. Verified against the live CloudFront bundle: all eight datasets load and
# BrainSpan expression values match the local files exactly.
#
# It also makes cross-dataset questions answerable at all: the bundle carries
# all eight published datasets, whereas the local files are BrainSpan only, so
# compare_datasets in local mode can never return more than one row.
#
# Costs of the default: it needs network access and downloads a 15 MB index on
# first run (cached under chatbot/cache/). Two things genuinely differ from the
# local CSVs, both documented in remote_loader:
#   - z-scores are the bundle's published values, ~0.30 higher than the local
#     ones because the local set standardises over 52,376 genes and the bundle
#     over the 30,687 it publishes. Rank order is identical (r = 1.00000), and
#     these are the values the gene view plots.
#   - the cell-type-controlled variance-partition model is absent from the
#     bundle; requesting it raises rather than silently serving the standard
#     model. That model exists only in BrainSpan_varPart_cellTypes.csv.
#
# BITHUB_LOCAL_DATA=1 forces the old local-file path — use it for the
# cell-type-controlled model, or to work offline.
#
# Exactly one source is loaded. In the default remote mode the local
# CSV/parquet is never touched, so the 150 MB matrix need not be present.

_local_flag = os.environ.get("BITHUB_LOCAL_DATA", "").lower() in ("1", "true", "yes")
# BITHUB_REMOTE_DATA is still honoured so existing .env files and scripts that
# set it keep working; it is now redundant with the default.
_remote_flag = os.environ.get("BITHUB_REMOTE_DATA", "").lower() in ("1", "true", "yes")
USE_REMOTE = _remote_flag or not _local_flag

if USE_REMOTE:
    from remote_loader import build_remote_brainspan_loader, make_session  # noqa: E402
    from source import DEFAULT_SOURCE, resolve as resolve_source  # noqa: E402

    # Where the data lives is resolved exactly as the website resolves it:
    # index and binary are siblings of the metadata.json named by
    # BITHUB_SOURCE. Commit 062f92e deleted frontend/static/metadata.json —
    # which this used to read — and moved the frontend to that sibling rule,
    # so following it here is what keeps the chat and the gene view on one
    # bundle. Point both at the same source and they cannot disagree; the
    # URL fields inside metadata.json are ignored because a deploy_local run
    # fills them with localhost. See source.py.
    try:
        SOURCE = resolve_source()
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"\nStartup failed: {exc}\n") from exc

    print(f"Data source: {SOURCE.label}")

    if SOURCE.is_local:
        # Reading a bundle off this filesystem is supported, but it is NOT what
        # the deployed site reads, and the two are different pipeline runs —
        # the local pipeline/output copy carries region-label differences the
        # published bundle does not. Silently answering from it would put the
        # chat and the plot beside it out of step with nothing to show for it,
        # so say so at startup as well as on /api/health.
        print(
            "  WARNING: this is a LOCAL bundle, not the published one the "
            "website reads.\n"
            "           Answers may differ from the site's figures. Unset "
            "BITHUB_SOURCE to use\n"
            f"           the published bundle ({DEFAULT_SOURCE})."
        )
        # Nothing to download, and expression.bin is range-read off disk
        # through the file:// adapter.
        index_path = SOURCE.local_index
    else:
        cache_dir = Path(os.environ.get("BITHUB_CACHE_DIR", Path(__file__).parent / "cache"))
        cache_dir.mkdir(parents=True, exist_ok=True)
        # Cache entry keyed on the source URL. A fixed 'out.hdf5' was fine
        # while there was one bundle; with a switchable source it silently
        # serves the previous source's download after a switch.
        index_path = cache_dir / SOURCE.cache_name()

        legacy = cache_dir / "out.hdf5"
        if not index_path.exists() and legacy.exists():
            # Pre-existing cache from before the rename. Reused rather than
            # re-downloaded, but only for the default source it was fetched
            # from, so a switched source never silently inherits it.
            if resolve_source(DEFAULT_SOURCE).data_url == SOURCE.data_url:
                print(f"  reusing existing cache {legacy.name} -> {index_path.name}")
                legacy.replace(index_path)

        if not index_path.exists():
            print(f"Downloading BITHub index from {SOURCE.data_url} …")
            tmp_path = index_path.with_suffix(".hdf5.partial")
            try:
                # Written to a temp name and renamed only on success: a
                # download interrupted midway would otherwise leave a
                # truncated file that every later start treats as cached.
                with make_session().get(SOURCE.data_url, stream=True, timeout=600) as resp:
                    resp.raise_for_status()
                    with open(tmp_path, "wb") as fh:
                        for chunk in resp.iter_content(1 << 20):
                            fh.write(chunk)
                tmp_path.replace(index_path)
            except Exception as exc:  # noqa: BLE001
                tmp_path.unlink(missing_ok=True)
                raise SystemExit(
                    f"\nStartup failed: could not download the BITHub index from "
                    f"{SOURCE.data_url}\n  ({type(exc).__name__}: {exc})\n\n"
                    "The chat reads the published bundle by default, which needs "
                    "network access on first run.\nTo read a bundle already on "
                    "disk instead:\n"
                    "    BITHUB_SOURCE=../pipeline/output\n"
                    "To run against the local BrainSpan CSVs: BITHUB_LOCAL_DATA=1\n"
                ) from exc
            print(f"  cached {index_path.stat().st_size / 1e6:.1f} MB at {index_path}")

    from remote_loader import DATASET_MATRIX  # noqa: E402

    # All eight published datasets, not just BrainSpan — the bundle carries
    # every one, so remote mode is what finally makes cross-dataset questions
    # answerable. Set BITHUB_REMOTE_DATASETS to a comma-separated subset to
    # narrow it.
    wanted = [d.strip() for d in os.environ.get(
        "BITHUB_REMOTE_DATASETS", ",".join(DATASET_MATRIX)).split(",") if d.strip()]

    remote_loaders = {}
    for name in wanted:
        try:
            remote_loaders[name] = build_remote_brainspan_loader(
                index_path, SOURCE.bin_url, dataset=name)
        except Exception as exc:  # noqa: BLE001
            # A dataset missing from the bundle is reported, not fatal — the
            # rest stay usable and DatasetRegistry marks it unavailable.
            print(f"  skipping {name}: {type(exc).__name__}: {exc}")

    if not remote_loaders:
        raise SystemExit(
            f"\nStartup failed: no dataset could be loaded from {index_path}.\n"
            "The file may be a truncated download — delete it and restart to "
            "re-fetch.\nTo run against the local BrainSpan files instead: "
            "BITHUB_LOCAL_DATA=1\n"
        )

    loader = remote_loaders.get("BrainSpan") or next(iter(remote_loaders.values()))
    registry = DatasetRegistry(remote_loaders)
    print(f"Data source: published bundle — {len(remote_loaders)} datasets "
          f"({', '.join(remote_loaders)})")
else:
    # A missing file raises DataFileMissing here rather than surfacing as a
    # 500 on the first question.
    try:
        loader = BrainSpanLoader(
            expr_path=EXPR_PATH,
            meta_path=META_PATH,
            vp_path=VP_PATH,
            vp_decon_path=VP_DECON_PATH,
            annotation_path=ANNOTATION_PATH,
        )
    except DataFileMissing as exc:
        raise SystemExit(f"\nStartup failed.\n\n{exc}\n")

    print("Data source: local files in", DATA_DIR)
    # Registry of every queryable dataset. Add another by constructing a
    # loader and adding it here — the API, tools and UI already handle multiple.
    registry = DatasetRegistry({"BrainSpan": loader})

# ── Request / response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    history: list = Field(default_factory=list, description="[{role, content}, ...]")
    datasets: list[str] = Field(
        default_factory=list,
        description=(
            "Dataset ids the user has selected. Empty means all loaded ones. "
            "Ids that are not loaded are reported back rather than ignored."
        ),
    )


class ChatResponse(BaseModel):
    response: str
    last_gene: str | None = None
    figure: dict | None = None          # first figure (back-compat)
    figures: list[dict] = []            # all figures from this turn
    tables: list[dict] = []             # render-ready tables from this turn
    literature: dict | None = None
    tools_used: list[str] = []
    datasets_used: list[str] = []
    datasets_unavailable: list[dict] = []
    elapsed_ms: int | None = None


# ── Routes ────────────────────────────────────────────────────────────────────

@app.get("/standalone", response_class=HTMLResponse)
def serve_standalone_chat():
    """
    The single-file chat page. Independent of the SvelteKit build, so it works
    even when the frontend has never been built — useful for testing the
    backend alone.
    """
    return HTMLResponse((Path(__file__).parent / "chat.html").read_text())


@app.post("/chat", response_model=ChatResponse,
          dependencies=[Depends(check_access)])
@app.post("/api/chat", response_model=ChatResponse,
          dependencies=[Depends(check_access)])
def chat(req: ChatRequest):
    started = time.perf_counter()
    selected, unavailable = registry.resolve(req.datasets)
    if not selected:
        raise HTTPException(
            status_code=400,
            detail=(
                "None of the selected datasets are loaded. Available: "
                + ", ".join(registry.available)
            ),
        )
    try:
        result = run_agent(
            req.message, registry, history=req.history, datasets=selected,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=500, detail=f"{type(exc).__name__}: {exc}")

    return ChatResponse(
        response=result["text"],
        datasets_used=selected,
        datasets_unavailable=unavailable,
        last_gene=result["last_gene"],
        figure=result.get("figure"),
        figures=result.get("figures", []),
        tables=result.get("tables", []),
        literature=result.get("literature"),
        tools_used=result.get("tools_used", []),
        elapsed_ms=int((time.perf_counter() - started) * 1000),
    )


@app.get("/api/datasets")
def datasets():
    """
    Every BITHub dataset, with `available` marking the ones actually loaded.

    The unavailable entries are returned deliberately: the multi-select shows
    the real scope of BITHub rather than implying one dataset is all there is.
    """
    return {
        "default": registry.default,
        "available": registry.available,
        "datasets": [
            {
                "id": e["id"], "label": e["id"], "available": e["loaded"],
                "assay": e["assay"],
                # The service reports log2(x+1) for per-sample values but the
                # pipeline's z-scores use log2(|x|+0.05); label the raw unit
                # only, so the two conventions cannot be conflated.
                "unit": e["unit"],
                "n_samples": (len(registry.get(e["id"]).shared_samples)
                              if e["loaded"] else e["n_samples"]),
                "n_genes": (int(len(registry.get(e["id"]).expr))
                            if e["loaded"] else None),
                "description": e["description"],
                **({} if e["loaded"]
                   else {"reason": "not yet loaded into the chat service"}),
            }
            for e in registry.catalog
        ],
        "comparison_note": (
            "Datasets use different units (RPKM, TPM, CPM). Cross-dataset "
            "comparisons are made on z-scored mean log2 expression."
        ),
    }


@app.get("/health")
@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "dataset": "BrainSpan",
        "n_genes": int(len(loader.expr)),
        "n_samples": len(loader.shared_samples),
        "model": MODEL,
        "unit": "log2(RPKM+1)",
        "data_source": "published_bundle" if USE_REMOTE else "local_files",
        # Which bundle, not just which mode. Two deployments can both say
        # "published_bundle" and be reading different pipeline runs; this is
        # the field that tells them apart, and the one to check when an answer
        # disagrees with the plot beside it.
        "source_url": SOURCE.metadata_url if USE_REMOTE else None,
        "source_is_local": SOURCE.is_local if USE_REMOTE else None,
        "frontend_mounted": FRONTEND_BUILD.is_dir(),
        "access_token_required": bool(ACCESS_TOKEN),
        "rate_limit": {"per_ip_hour": RATE_PER_IP_HOUR, "total_day": RATE_TOTAL_DAY},
        "questions_today": len(_day_hits),
    }


# ── Serve the built BITHub site (demo convenience) ────────────────────────────
#
# Mounting the static build here collapses the demo to ONE command and ONE
# origin: no second terminal, no CORS, no PUBLIC_CHAT_API. The whole site,
# including /ask, is served from the same process that answers the questions.
#
# This is for demos and local review, NOT how the site ships. In production
# the frontend is static files on S3/CloudFront and this service sits behind
# a separate URL — see the deployment checklist.
#
# The mount is LAST on purpose: StaticFiles at "/" is a catch-all, so every
# real route above must already be registered or it would be shadowed.

if FRONTEND_BUILD.is_dir():
    # adapter-static writes FLAT pages — build/ask.html, build/search.html —
    # not build/ask/index.html, so StaticFiles(html=True) 404s on /ask. This
    # handler resolves /<route> to <route>.html before the mount sees it.
    class FlatPageStatic(StaticFiles):
        """
        StaticFiles that also resolves /ask to ask.html.

        adapter-static writes FLAT pages (build/ask.html), not directories
        (build/ask/index.html), so html=True alone 404s on every route but /.
        Subclassing rather than adding a catch-all route keeps real files
        (favicon.ico, metadata.json) served normally — a route registered
        before the mount would shadow them, and metadata.json is what the
        site loads its entire dataset list from.

        Path traversal is handled upstream by StaticFiles.lookup_path, which
        rejects anything resolving outside the mounted directory.
        """

        async def get_response(self, path, scope):
            response = await super().get_response(path, scope)
            if response.status_code == 404 and "." not in path:
                return await super().get_response(f"{path}.html", scope)
            return response

    app.mount("/", FlatPageStatic(directory=FRONTEND_BUILD, html=True), name="site")
    print(f"Serving BITHub frontend from {FRONTEND_BUILD}")
else:
    @app.get("/", response_class=HTMLResponse)
    def serve_chat_fallback():
        """No frontend build present — fall back to the standalone page."""
        return HTMLResponse((Path(__file__).parent / "chat.html").read_text())

    print(
        f"No frontend build at {FRONTEND_BUILD} — serving the standalone chat "
        "page at /. Run `cd frontend && npm run build` to serve the full site."
    )
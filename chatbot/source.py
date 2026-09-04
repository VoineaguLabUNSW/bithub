"""
Where the data lives — resolved the same way the website resolves it.

Until commit 062f92e the frontend read ``data_url`` and ``bin_url`` out of
``metadata.json``, and the chat backend read the *same file* from
``frontend/static/metadata.json`` to learn where the bundle was. That commit
deleted ``frontend/static/metadata.json`` and changed the rule: the frontend
now takes the ``?source=`` URL, strips the filename, and fetches ``out.hdf5``
and ``expression.bin`` as SIBLINGS of whatever directory the metadata sits in::

    // frontend/src/lib/stores/core.js
    const obj = await getHDF5($metadata.url + '/out.hdf5', ...)
    const response = await fetch($metadata.url + '/expression.bin', {...})

So the URL fields inside metadata.json are now dead weight for locating data —
the *location of metadata.json itself* is the address. This module implements
that same rule server-side, which is what keeps the chat and the gene view
pointed at one bundle: give both the same source and they cannot disagree.

Why not keep reading the URL fields? Because the copy in ``pipeline/output/``
is written by a ``deploy_local: True`` run and says ``http://localhost:5501``.
Trusting those fields would send the chat to a dev server that isn't running,
while the site next to it — following the sibling rule — reads CloudFront. The
two would answer from different data and nothing would say so.

The source may be an http(s) URL, a ``file://`` URL, or a plain filesystem
path (file or directory). A local path is resolved to ``file://`` so that one
code path serves both; :mod:`remote_loader` mounts a Range-capable adapter for
that scheme.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import unquote, urlparse

#: The website's own default, copied from the ``createParam('source', …)`` call
#: in ``frontend/src/routes/+layout.svelte``. Keeping the literal here means a
#: chat started with no configuration reads exactly what a visitor to the
#: public site reads.
DEFAULT_SOURCE = "https://d33ldq8s2ek4w8.cloudfront.net/bithub/metadata.json"

INDEX_NAME = "out.hdf5"
BINARY_NAME = "expression.bin"


@dataclass(frozen=True)
class Source:
    """A resolved data source: where metadata, index and binary each live."""

    metadata_url: str
    data_url: str
    bin_url: str
    #: True when the bundle is on this filesystem, so the index needs no
    #: download and the binary can be range-read directly off disk.
    is_local: bool
    #: Local path of the index when ``is_local``; None otherwise.
    local_index: Path | None

    @property
    def label(self) -> str:
        """Short human description for startup logging."""
        if self.is_local:
            return f"local bundle at {Path(unquote(urlparse(self.data_url).path)).parent}"
        return f"remote bundle at {self.data_url.rsplit('/', 1)[0]}"

    def cache_name(self) -> str:
        """
        Cache filename for the downloaded index, keyed by source.

        A single fixed ``cache/out.hdf5`` was wrong as soon as the source
        became switchable: point the chat at a staging bundle, then back at
        production, and the first run's file is still sitting there and is
        silently reused. Keying on the URL means each source gets its own
        cache entry and switching can never serve the previous bundle.
        """
        digest = hashlib.sha256(self.data_url.encode()).hexdigest()[:12]
        return f"out-{digest}.hdf5"


def _looks_like_url(value: str) -> bool:
    return urlparse(value).scheme in ("http", "https", "file")


def resolve(source: str | None = None) -> Source:
    """
    Resolve a source into index and binary locations.

    ``source`` may name ``metadata.json`` directly or the directory holding
    it; either way the siblings are derived from the containing directory,
    which is exactly what the frontend does with ``?source=``. Falls back to
    ``$BITHUB_SOURCE`` and then to the website's own default.
    """
    raw = (source or os.environ.get("BITHUB_SOURCE") or DEFAULT_SOURCE).strip()
    if not raw:
        raise ValueError("Empty data source.")

    if not _looks_like_url(raw):
        # A filesystem path. Resolved eagerly so a typo fails here, naming the
        # path, rather than later as an opaque HDF5 open error.
        path = Path(raw).expanduser().resolve()
        if path.is_dir():
            directory = path
        elif path.exists():
            directory = path.parent
        else:
            raise FileNotFoundError(
                f"Data source not found: {path}\n"
                "Pass a metadata.json, the directory holding it, or an http(s) URL."
            )
        index = directory / INDEX_NAME
        binary = directory / BINARY_NAME
        missing = [p.name for p in (index, binary) if not p.exists()]
        if missing:
            raise FileNotFoundError(
                f"{directory} is not a BITHub bundle — missing {', '.join(missing)}.\n"
                "A bundle directory holds metadata.json, out.hdf5 and expression.bin."
            )
        return Source(
            metadata_url=(directory / "metadata.json").as_uri(),
            data_url=index.as_uri(),
            bin_url=binary.as_uri(),
            is_local=True,
            local_index=index,
        )

    parsed = urlparse(raw)
    # Strip a trailing filename the same way core.js does: everything up to the
    # last '/'. A directory URL given with a trailing slash keeps its meaning.
    base = raw[: raw.rindex("/")] if "/" in parsed.path else raw

    if parsed.scheme == "file":
        index = Path(unquote(urlparse(f"{base}/{INDEX_NAME}").path))
        return Source(
            metadata_url=raw,
            data_url=f"{base}/{INDEX_NAME}",
            bin_url=f"{base}/{BINARY_NAME}",
            is_local=True,
            local_index=index,
        )

    return Source(
        metadata_url=raw,
        data_url=f"{base}/{INDEX_NAME}",
        bin_url=f"{base}/{BINARY_NAME}",
        is_local=False,
        local_index=None,
    )

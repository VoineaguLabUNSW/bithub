"""
Read BITHub's published bundle instead of local CSV/parquet.

This is the Python equivalent of what frontend/src/lib/stores/core.js does in
the browser: open the HDF5 index, look up a gene's row, read its
(byteStart, byteEnd) pair, fetch exactly those bytes from expression.bin with
an HTTP Range request, inflate, and decode a RowData protobuf.

Why it matters: the chat and the website then read the SAME bytes, so a number
in a chat answer cannot disagree with the plot beside it. The local
BrainSpanLoader reads files whose provenance relative to the published bundle
is unverified.

Status: WORKING PROTOTYPE, exercised against a synthetic bundle built to the
structure pipeline/main.py writes (see tests/test_remote_loader.py). It has
NOT been run against the live CloudFront bundle. If that bundle was packed by
an older pipeline revision its group layout may differ — the failure would be
a KeyError naming the missing path, not silent wrong data.

    loader = BITHubRemoteLoader.from_metadata_url(
        "https://d33ldq8s2ek4w8.cloudfront.net/bithub/metadata.json")
    loader.gene_expression("SHANK3")
"""

from __future__ import annotations

import io
import io
import json
import sys
import zlib
from functools import lru_cache
from pathlib import Path
from urllib.parse import urljoin

import h5py
import numpy as np
import requests

# data_pb2 lives in pipeline/ and is imported by bare name there, so the
# pipeline directory has to be importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "pipeline"))
import data_pb2  # noqa: E402

# One canonicaliser for both sources, so a component name from the bundle and
# the same name from the local CSVs become the same internal key.
from data_loader import _clean_varpart_name  # noqa: E402


class _FileAdapter(requests.adapters.BaseAdapter):
    """
    Serve ``file://`` through requests, honouring Range.

    A bundle sitting in ``pipeline/output/`` is the normal case when working
    against the site's own data, and the alternative — telling everyone to run
    ``python -m http.server`` in another terminal before the chat will start —
    is a step that gets forgotten and fails as a connection error far from its
    cause. Mounting this means one code path reads both local and published
    bundles: :meth:`BrainSpanLoader._range_decode` issues the same Range
    request either way and cannot tell the difference.

    Only Range and whole-file GET are implemented, which is all the loader
    ever issues.
    """

    def send(self, request, **kwargs):                      # noqa: D102
        from urllib.parse import unquote, urlparse

        path = Path(unquote(urlparse(request.url).path))
        response = requests.Response()
        response.url = request.url
        response.request = request

        if not path.is_file():
            response.status_code = 404
            response.raw = io.BytesIO(b"")
            response.reason = "Not Found"
            return response

        rng = request.headers.get("Range", "")
        if rng.startswith("bytes="):
            first, last = rng[len("bytes="):].split("-")
            start, end = int(first), int(last)
            with open(path, "rb") as fh:
                fh.seek(start)
                body = fh.read(end - start + 1)
            response.status_code = 206          # matches the HTTP path's check
        else:
            body = path.read_bytes()
            response.status_code = 200

        response.raw = io.BytesIO(body)
        response.headers["Content-Length"] = str(len(body))
        return response

    def close(self):                                        # noqa: D102
        pass


def make_session() -> requests.Session:
    """A session that can read http(s) and local file:// bundles alike."""
    session = requests.Session()
    session.mount("file://", _FileAdapter())
    return session


class RemoteBundleError(RuntimeError):
    """Raised when the published bundle is unreachable or shaped unexpectedly."""


class BITHubRemoteLoader:
    """
    Reads one dataset out of a published BITHub bundle.

    Deliberately mirrors BrainSpanLoader's public surface (gene resolution,
    per-gene values, sample metadata, z-scores) so DatasetRegistry can hold
    either kind without the tools in agent.py changing.
    """

    def __init__(self, hdf5_path_or_file, dataset: str, bin_url: str | None = None,
                 matrix: str = "RPKM", session: requests.Session | None = None):
        self.dataset = dataset
        self.matrix = matrix
        self.session = session or make_session()
        self._h5 = (hdf5_path_or_file if isinstance(hdf5_path_or_file, h5py.File)
                    else h5py.File(hdf5_path_or_file, "r"))

        try:
            self._ranges = self._h5[f"metadata/{dataset}/matrices/{matrix}"]
            self._row_index = self._h5[f"data/{dataset}"][:]
            self._symbols = self._decode(self._h5["data/Gene Symbol"][:])
            self._ensembl = self._decode(self._h5["data/Ensembl ID"][:])
        except KeyError as exc:
            raise RemoteBundleError(
                f"Bundle does not contain the expected path for dataset "
                f"'{dataset}' / matrix '{matrix}': {exc}. Available datasets: "
                f"{list(self._h5.get('metadata', {}))}"
            ) from exc

        # The pipeline writes the binary's URL into the matrix dataset's
        # attributes. In the CURRENTLY PUBLISHED bundle that attribute is
        # 'http://localhost:5501\..\output-final-feb\expression.bin' — a
        # Windows local path left behind by a deploy_local run — so it cannot
        # be trusted. An explicit bin_url wins, and a localhost value is
        # rejected rather than silently attempted.
        self.bin_url = bin_url or self._ranges.attrs.get("path", "")
        if isinstance(self.bin_url, bytes):
            self.bin_url = self.bin_url.decode()
        if not self.bin_url:
            raise RemoteBundleError(
                "No expression.bin URL: neither passed in nor present as a "
                f"'path' attribute on metadata/{dataset}/matrices/{matrix}."
            )
        # The check applies only to the EMBEDDED attribute, never to a URL the
        # caller passed. An embedded localhost value is a deploy_local
        # leftover pointing at a machine that no longer exists; a caller
        # passing localhost (or file://) has deliberately chosen a local
        # bundle, which is now a supported source — see source.resolve.
        # Rejecting that too made a locally-served bundle unreadable even when
        # it was the thing the site itself was reading.
        if bin_url is None and ("localhost" in self.bin_url or "\\" in self.bin_url):
            raise RemoteBundleError(
                f"The bundle's embedded expression.bin URL is a local path "
                f"({self.bin_url!r}), left over from a deploy_local run. Pass "
                "bin_url= explicitly, or set BITHUB_SOURCE to the bundle's "
                "metadata.json (see chatbot/source.py)."
            )

        self._symbol_to_row = {s.upper(): i for i, s in enumerate(self._symbols)}
        self._ensembl_to_row = {e: i for i, e in enumerate(self._ensembl)}

    # ── construction ──────────────────────────────────────────────────────

    @classmethod
    def from_metadata_url(cls, metadata_url: str, dataset: str = "BrainSpan",
                          matrix: str = "RPKM", cache_dir: str | None = None):
        """
        Open the bundle that sits alongside a metadata.json.

        The index and binary are resolved as SIBLINGS of the metadata URL,
        which is the rule the website itself follows since commit 062f92e
        (see :mod:`source`). The URL fields inside metadata.json are ignored
        deliberately: a ``deploy_local`` run writes ``http://localhost:5501``
        into them, so trusting them sent this loader to a dev server that
        wasn't running — while the site next to it, following the sibling
        rule, read the real bundle.

        The index is downloaded whole — the browser does the same, and it is
        the small file. Only expression.bin is range-read.
        """
        from source import resolve

        src = resolve(metadata_url)
        session = make_session()

        if src.is_local:
            # Already on disk: no download, no cache entry.
            return cls(src.local_index, dataset=dataset, bin_url=src.bin_url,
                       matrix=matrix, session=session)

        cache = Path(cache_dir or Path(__file__).parent / "cache")
        cache.mkdir(parents=True, exist_ok=True)
        # Keyed on the source URL, not the bare filename: every bundle is
        # called out.hdf5, so a fixed name silently reuses the previous
        # source's download after a switch.
        local = cache / src.cache_name()

        if not local.exists():
            partial = local.with_suffix(".hdf5.partial")
            try:
                with session.get(src.data_url, stream=True, timeout=300) as r:
                    r.raise_for_status()
                    with open(partial, "wb") as f:
                        for chunk in r.iter_content(1 << 20):
                            f.write(chunk)
                partial.replace(local)
            except BaseException:
                # An interrupted download must not leave a truncated file that
                # every later start treats as a valid cache entry.
                partial.unlink(missing_ok=True)
                raise

        return cls(local, dataset=dataset, bin_url=src.bin_url,
                   matrix=matrix, session=session)

    # ── gene access ───────────────────────────────────────────────────────

    def resolve_gene(self, gene: str) -> int:
        """Gene symbol or Ensembl ID -> global row number."""
        key = gene.strip()
        row = self._symbol_to_row.get(key.upper())
        if row is None:
            row = self._ensembl_to_row.get(key)
        if row is None:
            raise ValueError(f"Gene '{gene}' not present in the {self.dataset} bundle.")
        return row

    @lru_cache(maxsize=4096)
    def _fetch_row(self, indexed_row: int) -> tuple:
        """
        One Range request for one gene's values.

        Cached because gene rows are immutable between pipeline runs, and a
        conversation revisits the same gene repeatedly.
        """
        # The live bundle stores ranges as an (n_rows, 2) array; handle a flat
        # layout too since older pipeline revisions wrote it that way.
        if self._ranges.ndim == 2:
            start, end = (int(v) for v in self._ranges[indexed_row])
        else:
            start = int(self._ranges[indexed_row * 2])
            end = int(self._ranges[indexed_row * 2 + 1])
        return self._range_decode(start, end)

    def _range_decode(self, start: int, end: int) -> tuple:
        """One Range request -> inflate -> decode RowData. Shared by expression
        and varPart, which live in the same binary."""
        resp = self.session.get(
            self.bin_url, headers={"Range": f"bytes={start}-{end - 1}"}, timeout=60
        )
        if resp.status_code != 206:
            raise RemoteBundleError(
                f"Expected HTTP 206 (partial content) from {self.bin_url}, got "
                f"{resp.status_code}. The host must support Range requests."
            )
        if len(resp.content) != end - start:
            raise RemoteBundleError(
                f"Range request returned {len(resp.content)} bytes, expected "
                f"{end - start}."
            )

        msg = data_pb2.RowData()
        msg.ParseFromString(zlib.decompress(resp.content))
        return tuple(msg.values)

    def gene_expression(self, gene: str) -> np.ndarray:
        """Per-sample values for one gene, in the bundle's sample order."""
        row = self.resolve_gene(gene)
        indexed = int(self._row_index[row])
        if indexed < 0:
            raise ValueError(f"'{gene}' has no data in {self.dataset}.")
        return np.asarray(self._fetch_row(indexed), dtype=np.float32)

    def gene_zscore(self, gene: str) -> float:
        """The precomputed z-score — the scale the gene view plots."""
        row = self.resolve_gene(gene)
        indexed = int(self._row_index[row])
        z = self._h5[f"metadata/{self.dataset}/zscores/All"]
        return float(z[indexed])

    # ── sample metadata ───────────────────────────────────────────────────

    @property
    @lru_cache(maxsize=1)
    def sample_metadata(self):
        """
        Sample metadata as a DataFrame, read once.

        Aggregate questions ("range of PMI", "which age intervals") need whole
        columns, so this is pulled up front rather than per request.
        """
        import pandas as pd

        root = self._h5[f"metadata/{self.dataset}/samples"]
        order = list(root.attrs.get("order", list(root)))
        cols = {}
        for name in order:
            values = root[name][:]
            cols[name] = self._decode(values) if values.dtype == object else values
        return pd.DataFrame(cols)

    # ── helpers ───────────────────────────────────────────────────────────

    @staticmethod
    def _decode(values) -> list:
        return [v.decode() if isinstance(v, bytes) else str(v) for v in values]

    @property
    def genes(self) -> list:
        return list(self._symbols)

    def close(self) -> None:
        self._h5.close()

    # ── transcripts ───────────────────────────────────────────────────────
    #
    # Transcript rows differ from gene rows in three ways, and all three are
    # handled here rather than by the caller:
    #
    #  1. The message is TableData, not RowData. Transcript IDs travel in their
    #     own `string_values` field — they are NOT row names and NOT a header
    #     column, so there is no index/header parsing and duplicate IDs would
    #     be harmless. `float_values` is n_transcripts x n_categories, row-major.
    #  2. The column titles live on the HDF5 dataset as attrs["categories"],
    #     not in the payload.
    #  3. Values are already averaged per category (age interval / tissue) and
    #     stored on the LINEAR scale — confirmed empirically across 128 genes,
    #     see transcript-pipeline-audit.md §A. The website applies log and
    #     z-score at render time (frontend/src/lib/utils/math.js), so anything
    #     quoting these numbers must say which scale it is using.

    def transcript_tables(self) -> list:
        """Transcript table names for this dataset, e.g. ['HIP Age Interval',
        'PFC Age Interval']. Empty for datasets without transcript data."""
        node = self._h5.get(f"metadata/{self.dataset}/transcripts")
        if node is None:
            return []
        return [n.decode() if isinstance(n, bytes) else str(n)
                for n in node.attrs.get("order", list(node))]

    def transcript_expression(self, gene: str, table: str | None = None):
        """
        One gene's transcript-level values.

        Returns (transcript_ids, categories, values) where values is
        (n_transcripts, n_categories) float32 on the LINEAR scale, or None if
        the gene has no transcript row in this table.

        `table` defaults to the dataset's only table when there is exactly one;
        with several (BrainSeq has HIP and PFC) it must be named, because
        silently picking one would attribute hippocampal numbers to a question
        about cortex.
        """
        available = self.transcript_tables()
        if not available:
            raise ValueError(
                f"{self.dataset} has no transcript data in the published "
                "bundle. Only BrainSeq (HIP/PFC Age Interval) and GTEx "
                "(ALL Tissues) carry transcript tables."
            )
        if table is None:
            if len(available) > 1:
                raise ValueError(
                    f"{self.dataset} has several transcript tables "
                    f"({available}); name one — they are different brain "
                    "regions and are not interchangeable."
                )
            table = available[0]
        if table not in available:
            raise ValueError(
                f"'{table}' is not a transcript table in {self.dataset}. "
                f"Available: {available}"
            )

        row = self.resolve_gene(gene)
        indexed = int(self._row_index[row])
        if indexed < 0:
            raise ValueError(f"'{gene}' has no data in {self.dataset}.")

        node = self._h5[f"metadata/{self.dataset}/transcripts/{table}"]
        start, end = (int(v) for v in (node[indexed] if node.ndim == 2
                                       else node[indexed * 2:indexed * 2 + 2]))
        if end <= start:
            return None

        resp = self.session.get(
            self.bin_url, headers={"Range": f"bytes={start}-{end - 1}"}, timeout=60
        )
        if resp.status_code != 206:
            raise RemoteBundleError(
                f"Expected HTTP 206 from {self.bin_url}, got {resp.status_code}."
            )

        msg = data_pb2.TableData()
        msg.ParseFromString(zlib.decompress(resp.content))
        if not msg.string_values:
            return None

        categories = [c.decode() if isinstance(c, bytes) else str(c)
                      for c in node.attrs["categories"]]
        ids = list(msg.string_values)
        values = np.asarray(msg.float_values, dtype=np.float32)

        expected = len(ids) * len(categories)
        if values.size != expected:
            raise RemoteBundleError(
                f"{gene}/{table}: got {values.size} floats, expected "
                f"{len(ids)} transcripts x {len(categories)} categories = {expected}."
            )
        return ids, categories, values.reshape(len(ids), len(categories))

    def transcript_frame(self, gene: str, table: str | None = None):
        """transcript_expression() as a DataFrame — transcript IDs as the
        index, categories as columns. Values stay linear-scale."""
        import pandas as pd

        got = self.transcript_expression(gene, table)
        if got is None:
            return None
        ids, categories, values = got
        return pd.DataFrame(values, index=pd.Index(ids, name="transcript_id"),
                            columns=categories)

    # ── varPart ───────────────────────────────────────────────────────────

    @lru_cache(maxsize=2048)
    def variance_partition(self, gene: str) -> dict:
        """Variance components for one gene, read by byte range like expression."""
        row = self.resolve_gene(gene)
        indexed = int(self._row_index[row])
        vp = self._h5.get(f"metadata/{self.dataset}/variance_partition")
        if vp is None:
            raise ValueError(
                f"{self.dataset} has no variance-partition results in the "
                "published bundle. The single-nucleus datasets (Cameron, HCA, "
                "Velmeshev) do not carry them."
            )
        # Canonicalised, not used raw: the bundle spells the dissection-score
        # component "Dissectionscore" whereas the local CSVs yield
        # "DissectionScore", and TECHNICAL_COMPONENTS is an exact set test that
        # would quietly omit it from technical_total.
        headings = [_clean_varpart_name(h.decode() if isinstance(h, bytes) else str(h))
                    for h in vp.attrs["heading"]]
        start, end = (int(v) for v in (vp[indexed] if vp.ndim == 2
                                      else vp[indexed * 2:indexed * 2 + 2]))
        values = self._range_decode(start, end)
        return dict(zip(headings, values))


class _LazyExpressionFrame:
    """
    Enough of a DataFrame for BrainSpanLoader's query methods.

    They only ever do `expr.loc[ensembl, columns]`, `ensembl in expr.index`
    and `expr.shape`, so a full in-memory matrix is unnecessary — each `.loc`
    triggers one cached Range request for that gene.
    """

    def __init__(self, remote, sample_names):
        self._remote = remote
        self._samples = list(sample_names)
        self.index = _EnsemblIndex(remote)
        self.columns = self._samples

    @property
    def shape(self):
        return (len(self._remote.genes), len(self._samples))

    def __len__(self):
        # main.py reports len(loader.expr) as the gene count in /api/health.
        return len(self._remote.genes)

    @property
    def loc(self):
        return self

    def __getitem__(self, key):
        import pandas as pd

        if isinstance(key, tuple):
            ensembl, cols = key
        else:
            ensembl, cols = key, self._samples
        series = pd.Series(self._remote.gene_expression(ensembl),
                           index=self._samples, dtype="float32")
        if isinstance(cols, slice):
            return series
        return series[list(cols)]


class _EnsemblIndex:
    """Index-like object so `ensembl in expr.index` works without the matrix."""

    def __init__(self, remote):
        self._remote = remote

    def __contains__(self, key):
        try:
            self._remote.resolve_gene(key)
            return True
        except ValueError:
            return False

    def __iter__(self):
        return iter(self._remote._ensembl)

    def __len__(self):
        return len(self._remote._ensembl)


class _LazyVarPart:
    """`vp.loc[ensembl]` / `ensembl in vp.index` backed by range reads."""

    def __init__(self, remote):
        self._remote = remote
        self.index = _EnsemblIndex(remote)

    @property
    def _dataset(self):
        """
        The varPart dataset, or None when this dataset has none.

        The three single-nucleus datasets (Cameron, HCA, Velmeshev) carry no
        variance_partition group in the published bundle. Raising KeyError here
        surfaced to the user as 'Missing required argument: "Unable to
        synchronously open object"', so absence is reported instead.
        """
        return self._remote._h5.get(
            f"metadata/{self._remote.dataset}/variance_partition")

    @property
    def available(self) -> bool:
        return self._dataset is not None

    @property
    def columns(self):
        import pandas as pd
        vp = self._dataset
        if vp is None:
            return pd.Index([])
        return pd.Index([_clean_varpart_name(h.decode() if isinstance(h, bytes) else str(h))
                         for h in vp.attrs["heading"]])

    @property
    def shape(self):
        vp = self._dataset
        if vp is None:
            return (0, 0)
        return (vp.shape[0], len(vp.attrs["heading"]))

    @property
    def loc(self):
        return self

    def __getitem__(self, key):
        import pandas as pd
        return pd.Series(self._remote.variance_partition(key), dtype="float64")


class _AbsentVarPart:
    """
    Stands in for the cell-type-controlled model, which the bundle lacks.

    Reports itself as empty rather than mirroring the standard model, so
    get_dataset_metadata advertises no cell-type components and nothing can
    accidentally serve one model under the other's name.
    """

    @property
    def columns(self):
        import pandas as pd
        return pd.Index([])

    @property
    def shape(self):
        return (0, 0)

    @property
    def index(self):
        return ()

    @property
    def loc(self):
        return self

    def __getitem__(self, key):
        raise ValueError(
            "Cell-type-controlled variance partition is not in the published "
            "bundle; it exists only in the local BrainSpan_varPart_cellTypes.csv."
        )


#: Which matrix each published dataset stores. The bundle mixes units — bulk
#: RNA-seq sets are RPKM or TPM, single-nucleus sets are CPM — so the matrix
#: name is per-dataset and cannot be defaulted to one value.
DATASET_MATRIX = {
    "BrainSpan": "RPKM", "BrainSeq": "RPKM", "HDBR": "RPKM",
    "GTEx": "TPM", "PsychENCODE": "TPM",
    "Cameron": "CPM", "HCA": "CPM", "Velmeshev": "CPM",
}


#: Bundle-global annotation, memoised per file. /data holds one row per gene
#: plus one presence column per dataset, so it is a property of the BUNDLE and
#: not of any dataset in it. Keyed on the HDF5 filename rather than cached on
#: the class so two bundles open in one process do not shadow each other.
_ANNOTATION_CACHE: dict = {}


def _bundle_annotation(h5):
    """
    (annotation DataFrame, {dataset: per-gene row index}) for this bundle.

    Returns (None, None) when the bundle has no /data group — the local CSV
    path — so the locus tools can refuse rather than invent coordinates.
    Absence is encoded as a negative row index, which is what lets "is this
    gene in Velmeshev" be answered without provoking a failed range request.
    """
    import pandas as pd            # local, matching the rest of this module

    key = getattr(h5, "filename", None) or id(h5)
    if key in _ANNOTATION_CACHE:
        return _ANNOTATION_CACHE[key]

    if "data" not in h5 or "Gene Symbol" not in h5["data"]:
        _ANNOTATION_CACHE[key] = (None, None)
        return _ANNOTATION_CACHE[key]

    decode = lambda v: np.array([
        s.decode() if isinstance(s, bytes) else str(s) for s in v
    ], dtype=object)

    ann_cols = {
        "symbol": decode(h5["data/Gene Symbol"][:]),
        "ensembl_id": decode(h5["data/Ensembl ID"][:]),
    }
    for raw, name in (("Gene Description", "description"),
                      ("chr", "chr"),
                      ("hg38 start", "start"),
                      ("hg38 end", "end")):
        if raw in h5["data"]:
            values = h5[f"data/{raw}"][:]
            ann_cols[name] = (decode(values) if values.dtype.kind in "SOU"
                              else values)
    annotation = pd.DataFrame(ann_cols)

    presence = {}
    for raw_name in h5["data"]:
        name = (raw_name.decode() if isinstance(raw_name, bytes)
                else str(raw_name))
        column = h5[f"data/{name}"]
        if (name in DATASET_MATRIX and column.dtype.kind in "iu"
                and column.shape[0] == len(annotation)):
            presence[name] = column[:]

    _ANNOTATION_CACHE[key] = (annotation, presence)
    return _ANNOTATION_CACHE[key]


def build_remote_brainspan_loader(hdf5_path, bin_url, dataset="BrainSpan",
                                  matrix=None):
    """
    A BrainSpanLoader whose data comes from the published bundle.

    Returns an object satisfying the same contract the tools use — the eleven
    query methods, plus `expr` / `meta` / `vp` / `gene_zscore` / the symbol
    maps — so `DatasetRegistry` and `agent.py` need no changes. Expression and
    varPart rows are fetched lazily per gene; sample metadata and z-scores are
    read once from the index.
    """
    import pandas as pd
    from data_loader import AGE_INTERVAL_ORDER, METADATA_COLUMNS, BrainSpanLoader

    remote = BITHubRemoteLoader(
        hdf5_path, dataset=dataset, bin_url=bin_url,
        matrix=matrix or DATASET_MATRIX.get(dataset, "RPKM"),
    )
    h5 = remote._h5

    loader = BrainSpanLoader.__new__(BrainSpanLoader)   # skip the file-reading __init__

    sample_names = remote._decode(h5[f"metadata/{dataset}/sample_names"][:])

    # Sample metadata, normalised to the same internal names the local loader
    # uses so the query methods and figure builders are unchanged.
    root = h5[f"metadata/{dataset}/samples"]
    cols = {}
    for name in root.attrs.get("order", list(root)):
        name = name.decode() if isinstance(name, bytes) else str(name)
        values = root[name][:]
        cols[METADATA_COLUMNS.get(name, name)] = (
            remote._decode(values) if values.dtype.kind in "SO" else values
        )
    meta = pd.DataFrame(cols)
    meta["SampleID"] = sample_names

    loader.meta = meta
    loader.shared_samples = sample_names
    # Per-dataset quantification unit. Without this every payload said RPKM,
    # so a GTEx (TPM) or Velmeshev (CPM) answer was labelled with the wrong
    # quantity and attributed to BrainSpan.
    loader.matrix_name = remote.matrix
    loader.dataset_id = dataset
    loader.expr = _LazyExpressionFrame(remote, sample_names)
    # The bundle carries ONE variance_partition model, and its values do not
    # match either local file: for SHANK3, Period is 0.615 in the bundle vs
    # 0.679 (BrainSpan_varPart.csv) and 0.603 (…_cellTypes.csv). Across eight
    # spot-checked genes the mean absolute difference is ~0.13, and GFAP
    # differs by 0.39 — these are separate variancePartition runs, not a
    # formatting difference.
    #
    # The bundle's values are the ones the gene view plots, so they are what a
    # user sees on screen; that is why they are used here. But cell-type
    # control is NOT available remotely — `cell_type_controlled=True` would
    # silently return the same numbers, so get_variance_partition is wrapped
    # below to say so instead.
    loader.vp = _LazyVarPart(remote)
    loader.vp_decon = _AbsentVarPart()
    loader.age_intervals = [a for a in AGE_INTERVAL_ORDER
                            if a in set(meta.get("AgeInterval", []))]

    # Published z-scores — the number the gene view plots. No recomputation,
    # so no gene-population mismatch.
    z = h5[f"metadata/{dataset}/zscores/All"][:]
    ens_by_row = {e: int(remote._row_index[i])
                  for i, e in enumerate(remote._ensembl)
                  if int(remote._row_index[i]) >= 0}
    loader.gene_zscore = pd.Series(
        {e: float(z[idx]) for e, idx in ens_by_row.items()}, dtype="float64"
    )

    loader.symbol_to_ensembl = {s.upper(): e for s, e in
                                zip(remote._symbols, remote._ensembl)}
    loader.ensembl_to_symbol = dict(zip(remote._ensembl, remote._symbols))
    loader._zscore_mu = loader._zscore_sd = float("nan")   # not recomputed here
    loader.remote = remote

    # Genomic annotation, from the bundle's /data group. Present only on this
    # path: the local CSV carries ensembl_id/gene_symbol/gene_name/entrez_id
    # and no coordinates, so the locus tools degrade honestly rather than
    # inventing positions. `presence` maps dataset -> per-gene row index, with
    # -1 for absent, which is how "is this gene in Velmeshev" is answered
    # without a failed fetch.
    # Built ONCE per bundle and shared by every loader, not rebuilt per
    # dataset: /data is a bundle-global table (one row per gene, a presence
    # column per dataset), so eight loaders each holding their own copy cost
    # ~45 MB of duplicate rows and pushed the all-eight footprint from 438 MB
    # to 499 MB — past the headroom on a 512 MB tier. Keyed on the resolved
    # file path so a second bundle in the same process still gets its own.
    annotation, presence = _bundle_annotation(h5)
    loader.annotation = annotation
    loader.gene_presence = presence

    # Refuse the cell-type-controlled model rather than quietly serving the
    # standard one under that label.
    _base_vp = loader.get_variance_partition

    def get_variance_partition(gene, cell_type_controlled=False):
        if cell_type_controlled:
            raise ValueError(
                "The published bundle contains one variance-partition model "
                "and it is not cell-type controlled. That model exists only in "
                "the local BrainSpan_varPart_cellTypes.csv, which is a "
                "different run from the bundle's — reporting one as the other "
                "would be wrong."
            )
        result = _base_vp(gene, cell_type_controlled=False)
        result["model"] = "published_bundle"
        result["source"] = "metadata/%s/variance_partition" % dataset
        return result

    loader.get_variance_partition = get_variance_partition
    return loader

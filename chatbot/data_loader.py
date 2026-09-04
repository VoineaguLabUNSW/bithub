"""
Data access layer for the BITHub chatbot.

The CSVs exported from the R pipeline use display-formatted column names
("Age (Numeric)", "Proportion of Neurons (MultiBrain)") and the
variancePartition outputs carry backtick-quoted names ("`PMI (hours)`").
Rather than scatter those literals through the code, every raw name is
normalised once at load time to a stable internal key. Add a dataset by
extending the maps below, not by renaming things at the call site.
"""

import re
from pathlib import Path

import numpy as np
import pandas as pd

# Raw metadata header -> internal key used everywhere downstream.
METADATA_COLUMNS = {
    "SampleID": "SampleID",
    "Age Interval": "AgeInterval",
    "Age (Numeric)": "AgeNumeric",
    "Period": "Period",
    "DonorID": "DonorID",
    "Sex": "Sex",
    "Ethnicity": "Ethnicity",
    "Structure Acronym": "StructureAcronym",
    "Regions": "Regions",
    "Proportion of Neurons (MultiBrain)": "Neurons",
    "Proportion of Astrocytes (MultiBrain)": "Astrocytes",
    "Proportion of Microglia (MultiBrain)": "Microglia",
    "Proportion of Oligodendrocytes (MultiBrain)": "Oligodendrocytes",
    "Proportion of Endothelia (MultiBrain)": "Endothelia",
    "Hemisphere": "Hemisphere",
    "RIN": "RIN",
    "Dissection Score": "DissectionScore",
    "PMI (hours)": "PMI",
    "pH": "pH",
    # Single-nucleus annotation columns (Cameron, HCA, Velmeshev). Without
    # these the internal name kept its spaces ("Major Cell Type"), so
    # _require_column and the cell-type tool could not resolve it from a
    # canonical name. "Major Cell Type" is the only one all three carry.
    "Major Cell Type": "MajorCellType",
    "Cell Type": "CellType",
    "Cortical Layer": "CorticalLayer",
    "Class": "Class",
    "Subclass": "Subclass",
    "Diagnosis": "Diagnosis",
}

CELL_TYPE_COLUMNS = [
    "Neurons", "Astrocytes", "Microglia", "Oligodendrocytes", "Endothelia",
]

# Variance components that are technical rather than biological. Used to
# compute the caveat the agent is required to surface on every varPart answer.
TECHNICAL_COMPONENTS = {"RIN", "PMI", "pH", "DissectionScore"}

# Developmental ordering for trajectory queries. BrainSpan spans 8 pcw to
# ~40 yrs; intervals absent from the data are dropped at runtime.
AGE_INTERVAL_ORDER = [
    "4-7pcw", "8-9pcw", "10-12pcw", "13-15pcw", "16-18pcw", "19-24pcw",
    "25-38pcw", "0-5mos", "6-18mos", "19mos-5yrs", "6-11yrs", "12-19yrs",
    "20-29yrs", "30-39yrs", "40-49yrs", "50-59yrs", "60-69yrs", "70-79yrs",
    "80-89yrs", "90-99yrs",
]

# Everything from 0-5mos onward is postnatal.
_FIRST_POSTNATAL_INDEX = AGE_INTERVAL_ORDER.index("0-5mos")


# Every internal key a variance component can legitimately carry, indexed by
# lowercase. The published bundle writes its own casing ("Dissectionscore")
# while the local CSVs produce "DissectionScore", and TECHNICAL_COMPONENTS
# membership is an exact set test — so an unmatched spelling does not error,
# it silently drops that covariate out of technical_total and understates the
# one number a reader most needs. Canonicalising case-insensitively makes both
# sources land on the same key.
_CANONICAL_COMPONENTS = {
    v.lower(): v for v in list(METADATA_COLUMNS.values()) + ["Residuals"]
}


def _clean_varpart_name(name: str) -> str:
    """
    '`PMI (hours)`' -> 'PMI'. varPart wraps names containing spaces in backticks.

    Also folds case-only variants onto one internal key, so the local CSVs and
    the published bundle agree on component names (see _CANONICAL_COMPONENTS).
    """
    stripped = name.strip().strip("`").strip()
    if stripped in METADATA_COLUMNS:
        return METADATA_COLUMNS[stripped]
    squashed = re.sub(r"[^0-9A-Za-z]+", "", stripped)
    return _CANONICAL_COMPONENTS.get(squashed.lower(), squashed)


# Must equal LOG2_OFFSET in pipeline/main.py — the z-scores computed here are
# compared against ones the pipeline wrote, so a divergence silently puts the
# chat and the gene view on different scales.
PIPELINE_LOG2_OFFSET = 0.05

# The eight datasets BITHub integrates. `loaded` is set at runtime by the
# loader registry — only datasets with files on disk can actually be queried.
#
# Note the unit column: RPKM, TPM and CPM are all present. This is why
# cross-dataset comparison happens in z-units and never in raw values.
DATASET_CATALOG = [
    {"id": "BrainSpan",   "assay": "bulk RNA-seq",  "unit": "RPKM", "n_samples":   524,
     "description": "Post-mortem human brain, 8 pcw to ~40 yrs."},
    {"id": "BrainSeq",    "assay": "bulk RNA-seq",  "unit": "RPKM", "n_samples":   900,
     "description": "DLPFC and hippocampus across the lifespan."},
    {"id": "GTEx",        "assay": "bulk RNA-seq",  "unit": "TPM",  "n_samples":  2642,
     "description": "Adult multi-region brain."},
    {"id": "HDBR",        "assay": "bulk RNA-seq",  "unit": "RPKM", "n_samples":   649,
     "description": "Human developmental biology resource, prenatal."},
    {"id": "PsychENCODE", "assay": "bulk RNA-seq",  "unit": "TPM",  "n_samples":  1369,
     "description": "Adult cortex, psychiatric and control."},
    {"id": "Cameron",     "assay": "snRNA-seq",     "unit": "CPM",  "n_samples": 69284,
     "description": "Single-nucleus, developing human brain."},
    {"id": "HCA",         "assay": "snRNA-seq",     "unit": "CPM",  "n_samples": 46958,
     "description": "Human Cell Atlas brain subset."},
    {"id": "Velmeshev",   "assay": "snRNA-seq",     "unit": "CPM",  "n_samples": 81215,
     "description": "Single-nucleus, ASD and control cortex."},
]


class DatasetRegistry:
    """
    Holds every loaded dataset and answers cross-dataset questions.

    Today only BrainSpan has files on disk. The registry exists so that the
    multi-select UI, the API contract and the tools all work against a set of
    datasets rather than one hardcoded loader — adding a second dataset is a
    catalog entry plus a loader instance, not a rewrite.

    It is deliberately strict about what it cannot answer: a request naming
    datasets that are not loaded returns them in `unavailable` rather than
    quietly answering from whatever happens to be present.
    """

    def __init__(self, loaders: dict):
        self.loaders = loaders

        # Loaders label their own output ("dataset": ...), so they must know
        # which dataset they are. Without this every payload said "BrainSpan"
        # regardless of which dataset produced it — a mislabelled answer is
        # worse than a missing one.
        for dataset_id, loader in loaders.items():
            setattr(loader, "dataset_id", dataset_id)

        self.catalog = [
            {**entry, "loaded": entry["id"] in loaders} for entry in DATASET_CATALOG
        ]
        self.default = next(iter(loaders), None)

    @property
    def available(self) -> list:
        return list(self.loaders)

    def get(self, dataset_id: str):
        try:
            return self.loaders[dataset_id]
        except KeyError:
            raise ValueError(
                f"Dataset '{dataset_id}' is not loaded. Available: "
                + (", ".join(self.loaders) or "none")
            )

    def resolve(self, requested) -> tuple:
        """Split a requested list into (loaded ids, unavailable ids)."""
        if not requested:
            return list(self.loaders), []
        if isinstance(requested, str):
            requested = [requested]
        known = {e["id"].lower(): e["id"] for e in self.catalog}
        ok, missing = [], []
        for name in requested:
            canonical = known.get(str(name).strip().lower())
            if canonical is None:
                missing.append({"dataset": str(name), "reason": "not a BITHub dataset"})
            elif canonical in self.loaders:
                if canonical not in ok:
                    ok.append(canonical)
            else:
                missing.append({
                    "dataset": canonical,
                    "reason": "not yet loaded into the chat service",
                })
        return ok, missing

    def compare_expression(self, gene: str, datasets=None) -> dict:
        """
        Compare one gene across datasets on the z-scored scale.

        Returns a row per queried dataset plus an explicit `unavailable` list
        and, when fewer than two datasets could be queried, a
        `comparison_possible: False` flag. The agent is instructed to surface
        that rather than present a single-dataset answer as corroboration.
        """
        requested, unavailable = self.resolve(datasets)

        rows, not_found = [], []
        for ds_id in requested:
            loader = self.loaders[ds_id]
            entry = next(e for e in self.catalog if e["id"] == ds_id)
            try:
                ensembl = loader._resolve_gene(gene)
            except ValueError:
                not_found.append(ds_id)
                continue
            rows.append({
                "dataset": ds_id,
                "symbol": loader.ensembl_to_symbol.get(ensembl, gene),
                "zscore": round(float(loader.gene_zscore.loc[ensembl]), 3),
                # Reported in the dataset's own unit for context only; the
                # pipeline's log offset is used so this matches the z-score
                # it sits beside rather than being a third convention.
                "mean_log2": round(
                    float(np.log2(
                        np.abs(loader.expr.loc[ensembl, loader.shared_samples]
                               .to_numpy(dtype=np.float64))
                        + PIPELINE_LOG2_OFFSET
                    ).mean()), 3),
                "native_unit": f"log2({entry['unit']}+0.05)",
                "n_samples": len(loader.shared_samples),
            })

        result = {
            "gene": gene,
            "datasets_queried": [r["dataset"] for r in rows],
            "unavailable": unavailable,
            "gene_not_found_in": not_found,
            "comparison_possible": len(rows) >= 2,
            "results": rows,
            "scale_note": (
                "zscore is mean log2 expression standardised across genes "
                "within each dataset — the same transform the BITHub gene view "
                "plots. It is the only field comparable between datasets, "
                "because BITHub mixes RPKM, TPM and CPM. Never compare "
                "mean_log2 across datasets."
            ),
        }
        if rows:
            result["table"] = make_table(
                title=f"{gene} across datasets (z-scored)",
                columns=[
                    {"key": "dataset", "label": "Dataset"},
                    {"key": "zscore", "label": "Z-score", "align": "right", "format": "2dp"},
                    {"key": "mean_log2", "label": "Mean log2", "align": "right", "format": "2dp"},
                    {"key": "native_unit", "label": "Native unit"},
                    {"key": "n_samples", "label": "Samples", "align": "right"},
                ],
                rows=rows,
                footnote=(
                    "Z-score is comparable across datasets; mean log2 is in each "
                    "dataset's own unit and is not."
                ),
            )
        if not result["comparison_possible"]:
            result["warning"] = (
                f"Only {len(rows)} dataset could be queried, so this is NOT a "
                "cross-dataset comparison. Say so explicitly — do not present a "
                "single-dataset result as corroboration across datasets."
            )
        return result


# Plotting constants. Gradient matches frontend/src/lib/utils/colors.js so
# heatmaps read the same as the z-score colouring elsewhere on the site.
GRADIENT_COLORS = ["#0b06b8", "#ffffff", "#b80641"]
CATEGORICAL_COLORS = [
    "#cf648a", "#4363d8", "#3cb44b", "#f58231", "#911eb4",
    "#008080", "#9a6324", "#e6194b", "#46f0f0", "#808000",
    "#000075", "#808080",
]
MARKER_SYMBOLS = ["circle", "diamond", "square", "triangle-up", "x", "star"]

MAX_HEATMAP_GENES = 60

# Friendlier axis labels for the columns most often plotted.
X_AXIS_LABELS = {
    "AgeNumeric": "Age (years relative to birth)",
    "AgeInterval": "Age interval",
    "PMI": "PMI (hours)",
    "RIN": "RIN",
    "pH": "pH",
    "DissectionScore": "Dissection score",
    "Regions": "Region",
    "StructureAcronym": "Structure",
    "Neurons": "Neuron fraction",
    "Astrocytes": "Astrocyte fraction",
    "Microglia": "Microglia fraction",
    "Oligodendrocytes": "Oligodendrocyte fraction",
    "Endothelia": "Endothelia fraction",
}


def make_table(title, columns, rows, footnote=None,
               highlight_row=None, highlight_note=None) -> dict:
    """
    Build a render-ready table.

    Tabular results are returned as structured data rather than left to the
    model to format, so the numbers the user sees are the numbers the tool
    computed. `columns` is [{key, label, align?, format?}]; rows are dicts
    keyed by `key`. format: '2dp' | '3dp' | 'pct' | None.
    """
    keys = [c["key"] for c in columns]
    return {
        "type": "table",
        "title": title,
        "columns": columns,
        "rows": [[row.get(k) for k in keys] for row in rows],
        "footnote": footnote,
        "highlight_row": highlight_row,
        "highlight_note": highlight_note,
    }


#: Fixed colours for variance components, so the same covariate is the same
#: colour in every answer and across the site. Biological drivers get saturated
#: hues, cell-type fractions cooler ones, technical covariates warm/amber (they
#: are the ones a reader should notice), residuals grey.
VARIANCE_COLORS = {
    "Period":            "#f58231",
    "AgeNumeric":        "#e6884a",
    "Regions":           "#cf648a",
    "DonorID":           "#911eb4",
    "Sex":               "#9a6324",
    "Ethnicity":         "#808000",
    "Neurons":           "#4363d8",
    "Astrocytes":        "#3cb44b",
    "Microglia":         "#46b3b3",
    "Oligodendrocytes":  "#008080",
    "Endothelia":        "#7ac4a0",
    "RIN":               "#e8b32a",
    "PMI":               "#d99a1f",
    "pH":                "#c98a10",
    "DissectionScore":   "#b87a00",
    "Residuals":         "#9ca3af",
}

#: Components below this fraction are grouped into an "Other" segment. A 0.06%
#: sliver is invisible in a bar and adds a legend entry for nothing; the exact
#: values stay available in `components`.
VARIANCE_BAR_MIN_FRACTION = 0.01


def _technical_footnote(technical: dict) -> str | None:
    """
    State the technical share, avoiding a misleading rounded "0.0%".

    Technical covariates are the ones a reader most needs to notice — a large
    share means the signal may be tissue quality rather than biology — so a
    total that rounds to zero should say "under 0.1%", not "0.0%".
    """
    if not technical:
        return None
    total = sum(technical.values()) * 100
    if total < 0.05:
        return "Technical covariates (RIN, PMI, pH, dissection score) total under 0.1%."
    return (f"Technical covariates (RIN, PMI, pH, dissection score) total "
            f"{total:.1f}%.")


# ── Statistical guards ────────────────────────────────────────────────────────
#
# Four of the tools below run a hypothesis test, and two failure modes make a
# test look far more convincing than it is. Both are properties of BITHub's
# data rather than of any one query, so they are handled here once rather than
# left to the model to remember.
#
# 1. PSEUDOREPLICATION. The single-nucleus datasets have thousands of nuclei
#    per donor (HCA: 46,958 nuclei from 3 donors). Nuclei from one donor are
#    not independent replicates of the biology being tested, so a nucleus-level
#    test answers "are these two piles of nuclei different", not "do these two
#    groups of people differ". Measured on Velmeshev SHANK3 in excitatory
#    neurons, the same effect size gives p=1.6e-03 at nucleus level and p=0.36
#    at donor level — a 226x inflation. Across genes the inflation ranged from
#    1x to >1e28, so there is no fixed correction; the test has to be run on
#    donor means.
#
# 2. SMALL GROUPS. PsychENCODE's Affective Disorder group is n=8 with d=-1.05
#    and p=4.6e-05. Large effect, tiny group, and nothing in the numbers says
#    so. Groups below MIN_GROUP_N are still reported but flagged.

#: Below this many independent units a group is reported with a warning. Eight
#: is not a principled threshold — it is the size of PsychENCODE's smallest
#: diagnosis group, i.e. the case that must not pass unremarked.
MIN_GROUP_N = 10

#: Above this ratio of observations to donors, a group comparison is run on
#: donor means rather than raw observations. 1.5 rather than 1.0 so a bulk set
#: with a handful of repeat donors is not needlessly aggregated.
PSEUDOREPLICATION_RATIO = 1.5


def _welch(a, b) -> dict:
    """
    Welch's t-test plus Cohen's d. Welch rather than Student because the
    diagnosis groups differ in both size and spread.
    """
    from scipy import stats
    a = np.asarray(a, dtype=float)
    b = np.asarray(b, dtype=float)
    a = a[~np.isnan(a)]
    b = b[~np.isnan(b)]
    if len(a) < 2 or len(b) < 2:
        return {"t": None, "p": None, "cohens_d": None,
                "reason": "need at least 2 observations per group"}
    t, p = stats.ttest_ind(a, b, equal_var=False)
    pooled = np.sqrt((a.var(ddof=1) + b.var(ddof=1)) / 2)
    d = float((a.mean() - b.mean()) / pooled) if pooled > 0 else None
    return {
        "t": round(float(t), 3),
        "p": float(p),
        "cohens_d": None if d is None else round(d, 3),
    }


def make_statistical_note(n_observations, n_donors, unit_of_analysis,
                          group_sizes=None, aggregated=False,
                          covariate_warning=None, extra=None) -> dict:
    """
    The caveat block returned alongside any inferential result.

    Returned as structured data *and* as a `text` sentence. The model reliably
    repeats what a payload tells it and reliably omits what it does not, so a
    caveat that exists only in the system prompt is a caveat that goes missing
    on the answers where it matters. `text` is written to be quotable verbatim.
    """
    warnings = []

    if aggregated:
        warnings.append(
            f"Observations were aggregated to donor means before testing "
            f"({n_observations:,} observations from {n_donors} donors). The "
            f"effective sample size is {n_donors}, not {n_observations:,}."
        )
    elif n_donors and n_observations and n_observations > n_donors:
        warnings.append(
            f"{n_observations:,} observations come from {n_donors} donors; "
            f"treat {n_donors} as the effective sample size."
        )

    small = [g for g in (group_sizes or {}).items() if g[1] < MIN_GROUP_N]
    if small:
        warnings.append(
            "Small group(s): "
            + ", ".join(f"{name} n={n}" for name, n in sorted(small, key=lambda g: g[1]))
            + f" (below {MIN_GROUP_N}). Effect sizes from groups this small are "
            "unstable and the p-value should not be read as evidence on its own."
        )

    if covariate_warning:
        warnings.append(covariate_warning)

    if extra:
        warnings.extend(extra if isinstance(extra, list) else [extra])

    return {
        "unit_of_analysis": unit_of_analysis,
        "n_observations": n_observations,
        "n_donors": n_donors,
        "aggregated_to_donor": bool(aggregated),
        "min_group_n_threshold": MIN_GROUP_N,
        "warnings": warnings,
        # One sentence, so the model has something to lift rather than
        # paraphrase. Paraphrase is where caveats lose their teeth.
        "text": (" ".join(warnings) if warnings else
                 f"Test run on {n_observations:,} independent "
                 f"{unit_of_analysis}-level observations; no aggregation needed."),
    }


def make_stacked_bar(title, segments, subtitle=None, footnote=None,
                     min_fraction=VARIANCE_BAR_MIN_FRACTION) -> dict:
    """
    A proportion bar: one horizontal bar of segments summing to 1, plus a legend.

    Variance decomposition is a part-of-whole result, and a table makes the
    reader do the comparison arithmetic themselves. A single bar shows at a
    glance that one covariate dominates — which is the finding — and keeps the
    exact fractions in the legend for anyone who wants them.

    `segments` is [{label, fraction}] in the order to draw. Segments below
    `min_fraction` are merged into "Other" so the bar stays legible; pass
    min_fraction=0 to keep every component separate.
    """
    kept, merged = [], []
    for segment in segments:
        fraction = float(segment["fraction"] or 0)
        if fraction < min_fraction and segment["label"] != "Residuals":
            merged.append(segment)
        else:
            kept.append({**segment, "fraction": fraction})

    if merged:
        kept.append({
            "label": "Other",
            "fraction": round(sum(float(s["fraction"] or 0) for s in merged), 6),
            "color": "#c8ccd4",
            "components": [
                {"label": s["label"], "fraction": round(float(s["fraction"] or 0), 6)}
                for s in sorted(merged, key=lambda s: -float(s["fraction"] or 0))
            ],
        })

    # Named drivers first (largest to smallest), then the merged "Other", then
    # Residuals last — the bar should read left-to-right as
    # explained -> minor -> unexplained.
    tail_order = {"Other": 1, "Residuals": 2}
    kept.sort(key=lambda s: (tail_order.get(s["label"], 0), -s["fraction"]))

    for segment in kept:
        segment.setdefault("color", VARIANCE_COLORS.get(segment["label"], "#9ca3af"))
        segment["percent"] = round(segment["fraction"] * 100, 1)

    total = sum(s["fraction"] for s in kept)
    return {
        "type": "stacked_bar",
        "title": title,
        "subtitle": subtitle,
        "segments": kept,
        "total": round(total, 6),
        "footnote": footnote,
    }


class DataFileMissing(RuntimeError):
    """Raised at startup so a missing file fails loudly instead of at first query."""


class BrainSpanLoader:
    #: Quantification unit of this loader's matrix. BITHub's eight datasets are
    #: a mix of RPKM, TPM and CPM, and a log2(TPM+1) value is not the same
    #: quantity as a log2(RPKM+1) one. Payloads read this rather than
    #: hardcoding "RPKM": labelling a GTEx answer as RPKM is the exact
    #: conflation the comment above `gene_zscore` warns about. The remote
    #: builder overwrites it per dataset from DATASET_MATRIX; the local loader
    #: only ever reads the BrainSpan RPKM export, so RPKM is the right default.
    matrix_name = "RPKM"

    #: Which dataset this loader serves. DatasetRegistry sets it per entry;
    #: the default keeps a bare loader (tests, local mode) self-describing.
    dataset_id = "BrainSpan"

    @property
    def unit(self) -> str:
        """Display unit for expression values, e.g. 'log2(RPKM+1)'."""
        return f"log2({self.matrix_name}+1)"

    def __init__(self, expr_path, meta_path, vp_path, vp_decon_path, annotation_path):
        paths = {
            "expression": Path(expr_path),
            "metadata": Path(meta_path),
            "variance partition": Path(vp_path),
            "variance partition (cell-type)": Path(vp_decon_path),
            "gene annotation": Path(annotation_path),
        }
        missing = [f"{label} -> {p}" for label, p in paths.items() if not p.exists()]
        if missing:
            raise DataFileMissing(
                "Required data file(s) not found:\n  " + "\n  ".join(missing)
                + "\n\nExpected under chatbot/data/. See chatbot/README.md."
            )

        print("Loading BrainSpan data...")

        # Prefer parquet when present. Measured on the 158 MB BrainSpan CSV:
        # 0.86s -> 0.05s warm-cache (best of 3), ~3x on a cold first read;
        # on-disk 158 MB -> 87 MB. Build it with scripts/build_parquet.py.
        parquet_path = Path(expr_path).with_suffix(".parquet")
        if parquet_path.exists():
            self.expr = pd.read_parquet(parquet_path)
            source = "parquet"
        else:
            self.expr = pd.read_csv(expr_path, index_col=0).astype(np.float32)
            source = "csv (slow — run scripts/build_parquet.py)"
        self.expr.index = self.expr.index.astype(str).str.strip()
        print(f"  Expression matrix: {self.expr.shape} [{source}]")

        meta = pd.read_csv(meta_path, index_col=0)
        unknown = set(meta.columns) - set(METADATA_COLUMNS)
        if unknown:
            print(f"  ! unmapped metadata columns ignored: {sorted(unknown)}")
        self.meta = meta.rename(columns=METADATA_COLUMNS)
        print(f"  Metadata: {self.meta.shape}")

        self.vp = pd.read_csv(vp_path, index_col=0)
        self.vp.columns = [_clean_varpart_name(c) for c in self.vp.columns]
        self.vp.index = self.vp.index.astype(str).str.strip()
        print(f"  Variance partition (standard): {self.vp.shape}")

        self.vp_decon = pd.read_csv(vp_decon_path, index_col=0)
        self.vp_decon.columns = [_clean_varpart_name(c) for c in self.vp_decon.columns]
        self.vp_decon.index = self.vp_decon.index.astype(str).str.strip()
        print(f"  Variance partition (cell-type controlled): {self.vp_decon.shape}")

        ann = pd.read_csv(annotation_path)
        ann["gene_symbol"] = ann["gene_symbol"].astype(str).str.strip()
        ann["ensembl_id"] = ann["ensembl_id"].astype(str).str.strip()
        ann = ann[ann.gene_symbol.ne("") & ann.gene_symbol.ne("nan")]
        self.symbol_to_ensembl = dict(zip(ann.gene_symbol.str.upper(), ann.ensembl_id))
        self.ensembl_to_symbol = dict(zip(ann.ensembl_id, ann.gene_symbol))
        self._gene_name = dict(zip(ann.gene_symbol.str.upper(), ann.get("gene_name", "")))
        print(f"  Gene annotation: {len(self.symbol_to_ensembl)} symbols mapped")

        # Sample columns shared between the matrix and the metadata. The join
        # is on SampleID; anything unmatched is excluded from every query.
        expr_cols = set(self.expr.columns)
        self.shared_samples = [s for s in self.meta["SampleID"] if s in expr_cols]
        if not self.shared_samples:
            raise DataFileMissing(
                "No SampleID in the metadata matches a column of the expression "
                "matrix — the two files are not from the same freeze."
            )
        print(f"  Samples joinable: {len(self.shared_samples)} / {len(self.meta)}")

        self.age_intervals = [
            a for a in AGE_INTERVAL_ORDER if a in set(self.meta["AgeInterval"].dropna())
        ]

        # Per-gene mean log expression, z-scored across genes within this
        # dataset — reproducing what pipeline/main.py writes to
        # metadata/<dataset>/zscores/All and the gene view plots as
        # "Z-Score Transformed Mean Log2 (Expression)".
        #
        # This is the ONLY scale on which datasets can be compared: BITHub's
        # eight sets are a mix of RPKM (BrainSpan, BrainSeq, HDBR), TPM (GTEx,
        # PsychENCODE) and CPM (Cameron, HCA, Velmeshev). A log2(RPKM+1) value
        # and a log2(TPM+1) value are not the same quantity, so any
        # cross-dataset claim must be made in z-units.
        #
        # PIPELINE_LOG2_OFFSET must stay equal to LOG2_OFFSET in
        # pipeline/main.py. It is 0.05, not 1 — and the difference is not
        # cosmetic. 47.7% of the BrainSpan matrix is exactly zero, and those
        # entries map to log2(0.05) = -4.32 rather than 0, which shifts the
        # mean and SD of the whole distribution. Using +1 here put ACTB at
        # z = +5.56 where the gene view shows +3.60: the chat would have
        # contradicted the plot beside it.
        #
        # These z-scores STILL do not match the published bundle exactly, and
        # cannot. Measured against the live out.hdf5: ACTB is +3.60 here but
        # +3.11 there. The transform is right; the population differs. The
        # pipeline standardises across the 30,687 genes it writes for
        # BrainSpan, while this matrix has 52,376 rows, so the mean and SD of
        # the reference distribution are not the same. Restricting to the
        # bundle's gene set reproduces the published values to within 0.02 for
        # 99.7% of genes (r = 0.9984).
        #
        # So: use these for RANKING and for comparing genes within this
        # service. Do NOT present them as the number on a gene-view axis. For
        # that, read metadata/<dataset>/zscores/All from the bundle —
        # remote_loader.BITHubRemoteLoader.gene_zscore does exactly that.
        gene_mean = np.log2(
            np.abs(self.expr[self.shared_samples].to_numpy(dtype=np.float64))
            + PIPELINE_LOG2_OFFSET
        ).mean(axis=1)
        self._zscore_mu = float(gene_mean.mean())
        self._zscore_sd = float(gene_mean.std(ddof=0))
        self.gene_zscore = pd.Series(
            (gene_mean - self._zscore_mu) / self._zscore_sd, index=self.expr.index
        )
        print(f"  Z-scores: mean log2 {self._zscore_mu:.3f} ± {self._zscore_sd:.3f}")
        print("Done.")

    # ── gene resolution ───────────────────────────────────────────────────

    def _resolve_gene(self, gene: str) -> str:
        """Accept a symbol or an Ensembl ID; return an Ensembl ID present in the matrix."""
        query = str(gene).strip()
        if query.upper().startswith("ENSG") and query in self.expr.index:
            return query

        ensembl = self.symbol_to_ensembl.get(query.upper())
        if ensembl is None:
            near = self.search_genes(query, limit=5)
            hint = f" Did you mean: {', '.join(near)}?" if near else ""
            raise ValueError(f"Gene symbol '{gene}' not found in annotation.{hint}")
        if ensembl not in self.expr.index:
            raise ValueError(
                f"Gene '{gene}' ({ensembl}) is annotated but absent from the "
                "BrainSpan expression matrix."
            )
        return ensembl

    def _expression_frame(self, gene: str):
        """Metadata joined to log2(RPKM+1) for one gene, restricted to joinable samples."""
        ensembl = self._resolve_gene(gene)
        values = np.log2(self.expr.loc[ensembl, self.shared_samples].astype(float) + 1)
        df = self.meta[self.meta["SampleID"].isin(self.shared_samples)].copy()
        df["expression"] = df["SampleID"].map(values).astype(float)
        return ensembl, df.dropna(subset=["expression"])

    # ── query methods (each returns JSON-serialisable primitives) ─────────

    #: Second grouping axis for get_expression, in order of preference.
    #: BrainSpan and the other bulk sets carry Period (Prenatal/Postnatal), but
    #: the single-nucleus sets (Cameron, HCA, Velmeshev) do not — they have no
    #: developmental axis at all, only cell types. Grouping by "Period"
    #: unconditionally raised KeyError on all three. AgeInterval is the
    #: fallback because it is the same developmental information at finer
    #: resolution; if neither exists the region means are still returned.
    _EXPRESSION_STRATA = ("Period", "AgeInterval")

    def get_expression(self, gene: str) -> dict:
        """Summary statistics rather than 524 raw rows — the agent only needs aggregates."""
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        stratum = next((c for c in self._EXPRESSION_STRATA if c in df.columns), None)
        has_regions = "Regions" in df.columns

        if stratum is None:
            # No developmental axis (single-nucleus). Return region means only
            # rather than failing — get_cell_type_expression is the tool that
            # answers the question these datasets are actually shaped for, and
            # the note below points there.
            by_period = pd.DataFrame(columns=["mean", "std", "count"])
            by_region_period = pd.Series(dtype="float64")
        else:
            by_period = (
                df.groupby(stratum)["expression"].agg(["mean", "std", "count"]).round(3)
            )
            by_region_period = (
                df.groupby(["Regions", stratum])["expression"].mean().round(3)
                if has_regions else pd.Series(dtype="float64")
            )

        region_period = {}
        for (region, period), value in by_region_period.items():
            region_period.setdefault(region, {})[period] = float(value)

        # Prenatal/Postnatal are Period's levels; AgeInterval has its own, and a
        # dataset with neither has none. Build the columns from what is present
        # so the table is never a grid of empty cells with the real numbers
        # stranded in expression_by_region_and_period.
        if stratum == "Period":
            level_keys = [lv for lv in ("Prenatal", "Postnatal")
                          if any(lv in v for v in region_period.values())]
        else:
            level_keys = sorted({lv for v in region_period.values() for lv in v},
                                key=lambda lv: (AGE_INTERVAL_ORDER.index(lv)
                                                if lv in AGE_INTERVAL_ORDER else 999))

        table_rows = []
        for region, levels in sorted(region_period.items()):
            row = {"region": region}
            row.update({lv: levels.get(lv) for lv in level_keys})
            if len(level_keys) == 2 and all(lv in levels for lv in level_keys):
                row["change"] = round(levels[level_keys[1]] - levels[level_keys[0]], 3)
            table_rows.append(row)

        table_columns = [{"key": "region", "label": "Region"}]
        table_columns += [{"key": lv, "label": lv, "align": "right", "format": "2dp"}
                          for lv in level_keys]
        if len(level_keys) == 2:
            table_columns.append(
                {"key": "change", "label": "Change", "align": "right", "format": "2dp"}
            )

        stratum_label = {"Period": "period", "AgeInterval": "age interval"}.get(
            stratum, "sample group"
        )
        note = (
            f"Values are {self.unit} computed from the {self.dataset_id} "
            f"{self.matrix_name} matrix. Units differ across BITHub datasets "
            "(RPKM / TPM / CPM), so these absolute numbers are NOT comparable "
            "with another dataset's — use compare_datasets, which z-scores, for "
            "cross-dataset statements. The BITHub gene-view plots show z-scored "
            "values, so absolute numbers here will not match those axes. Render "
            "'table' rather than retyping these numbers into prose."
        )
        if stratum is None:
            note += (
                f" {self.dataset_id} is single-nucleus and has no developmental "
                "axis, so no period/age breakdown is returned. Call "
                "get_cell_type_expression for the axis this dataset is "
                "actually resolved on."
            )

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "dataset": self.dataset_id,
            "unit": self.unit,
            "grouped_by": stratum,
            "n_samples": int(len(df)),
            "overall_mean": round(float(df["expression"].mean()), 3),
            "expression_by_period": {
                p: {"mean": float(r["mean"]), "sd": float(r["std"]), "n": int(r["count"])}
                for p, r in by_period.iterrows()
            },
            "expression_by_region_and_period": region_period,
            "table": make_table(
                title=f"{symbol} — mean expression by region"
                      + (f" and {stratum_label}" if stratum else "")
                      + f" ({self.dataset_id})",
                columns=table_columns,
                rows=table_rows,
                footnote=f"{self.unit}, {len(df)} samples, {self.dataset_id}.",
            ),
            "note": note,
        }

    #: Cell-type annotation columns for single-nucleus datasets, coarsest first.
    #: "Major Cell Type" is the one column all three snRNA-seq sets share
    #: (Cameron, HCA, Velmeshev), with 7-10 interpretable levels — the right
    #: default. The finer columns exist on some sets only and run to 91-120
    #: levels, which is too many to summarise usefully but is offered via the
    #: `resolution` argument. Names are the INTERNAL (canonicalised) forms.
    #: Distinct from the module-level CELL_TYPE_COLUMNS, which is the bulk
    #: deconvolution PROPORTIONS (numeric); these are annotation LABELS.
    #: CorticalLayer is an anatomical rather than a taxonomic grouping, but it
    #: is the same query shape — mean expression per annotation label — and HCA
    #: carries it, so it is offered through the same `resolution` argument
    #: rather than as a separate tool. It is listed last so it is never the
    #: default, and only appears for datasets that actually have the column.
    _CELL_TYPE_ANNOTATION_COLUMNS = ("MajorCellType", "Class", "Subclass",
                                     "CellType", "CorticalLayer")

    def cell_type_levels(self) -> dict:
        """
        Which cell-type groupings this dataset supports, and their levels.

        Discovered from the loaded metadata rather than hardcoded: the level
        names are not stable across pipeline freezes (Cameron's are 'OPC' /
        'Endothelial' in the Aug 2026 freeze but 'OPCs' / 'Endothelia' in the
        published one), so a hardcoded list would silently return nothing after
        a data update.
        """
        out = {}
        for col in self._CELL_TYPE_ANNOTATION_COLUMNS:
            if col in self.meta.columns:
                out[col] = sorted(self.meta[col].dropna().astype(str).unique())
        return out

    def get_cell_type_expression(self, gene: str, cell_type: str = None,
                                 resolution: str = "MajorCellType") -> dict:
        """
        Mean expression per cell type, for single-nucleus datasets.

        This is the axis snRNA-seq data is actually resolved on. The bulk sets
        have a developmental/regional axis and no cell types; these have cell
        types and (mostly) no developmental axis, so get_expression's
        region x period summary is the wrong shape for them.
        """
        levels = self.cell_type_levels()
        if not levels:
            raise ValueError(
                f"{self.dataset_id} has no cell-type annotation — it is a bulk "
                "tissue dataset, where each sample is a mixture of cell types. "
                "Use get_expression for regional/developmental summaries, or "
                "get_variance_partition, whose cell-type-proportion components "
                "are how cell-type signal is represented in bulk data. "
                "Cell-type resolved datasets: Cameron, HCA, Velmeshev."
            )

        key = METADATA_COLUMNS.get(str(resolution).strip(), str(resolution).strip())
        if key not in levels:
            raise ValueError(
                f"'{resolution}' is not a cell-type grouping in "
                f"{self.dataset_id}. Available: {', '.join(levels)}."
            )

        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)
        df = df.dropna(subset=[key])

        grouped = (
            df.groupby(key)["expression"].agg(["mean", "std", "count"]).round(3)
            .sort_values("mean", ascending=False)
        )
        if grouped.empty:
            raise ValueError(
                f"'{symbol}' has no {self.dataset_id} samples with a "
                f"{resolution} annotation."
            )

        # Enrichment against this gene's own mean across all cell types, so the
        # number answers "is it concentrated anywhere" rather than restating the
        # mean. Reported in log2 units, i.e. an additive difference.
        overall = float(df["expression"].mean())
        rows = [
            {
                "cell_type": ct,
                "mean": float(r["mean"]),
                "sd": None if pd.isna(r["std"]) else float(r["std"]),
                "n": int(r["count"]),
                "vs_dataset_mean": round(float(r["mean"]) - overall, 3),
            }
            for ct, r in grouped.iterrows()
        ]

        requested = None
        if cell_type is not None:
            want = str(cell_type).strip().lower()
            match = [r for r in rows if r["cell_type"].lower() == want]
            if not match:
                # Substring fallback: "microglia" should find "Microglia", and
                # level names drift between freezes.
                match = [r for r in rows if want in r["cell_type"].lower()]
            if not match:
                raise ValueError(
                    f"'{cell_type}' is not a {resolution} level in "
                    f"{self.dataset_id}. Available: "
                    f"{', '.join(levels[key])}."
                )
            requested = match[0]

        top = rows[0]
        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "dataset": self.dataset_id,
            "unit": self.unit,
            "resolution": key,
            "n_cell_types": len(rows),
            "n_samples": int(len(df)),
            "overall_mean": round(overall, 3),
            "highest": {"cell_type": top["cell_type"], "mean": top["mean"],
                        "vs_dataset_mean": top["vs_dataset_mean"]},
            "requested_cell_type": requested,
            "by_cell_type": rows,
            "table": make_table(
                title=f"{symbol} — mean expression by {key} ({self.dataset_id})",
                columns=[
                    {"key": "cell_type", "label": "Cell type"},
                    {"key": "mean", "label": f"Mean {self.unit}",
                     "align": "right", "format": "2dp"},
                    {"key": "sd", "label": "SD", "align": "right", "format": "2dp"},
                    {"key": "n", "label": "Nuclei", "align": "right"},
                    {"key": "vs_dataset_mean", "label": "vs mean",
                     "align": "right", "format": "2dp"},
                ],
                rows=rows,
                footnote=(
                    f"{self.unit}, {len(df)} nuclei across {len(rows)} cell "
                    f"types. 'vs mean' is the difference from this gene's mean "
                    f"over all {self.dataset_id} nuclei, in log2 units."
                ),
                highlight_row=(
                    rows.index(requested) if requested is not None else None
                ),
            ),
            "note": (
                f"Cell-type means from {self.dataset_id} ({self.unit}). "
                "These are per-nucleus values aggregated by annotation label, "
                "not deconvolved bulk estimates. Units differ across BITHub "
                "datasets, so do not compare these absolute numbers with a "
                "bulk RPKM/TPM dataset — use compare_datasets for that. "
                "Render 'table' rather than retyping the numbers."
            ),
        }

    def _donor_aggregate(self, df, group_cols):
        """
        Collapse observations to one row per donor per group, when needed.

        Returns (frame, aggregated, n_observations, n_donors). `aggregated` is
        False when the data is already one observation per donor, so the caller
        can report honestly rather than claiming an aggregation that was a
        no-op. See the PSEUDOREPLICATION note at module level for why this is
        not optional on the single-nucleus datasets.
        """
        n_obs = int(len(df))
        if "DonorID" not in df.columns:
            return df, False, n_obs, None

        n_donors = int(df["DonorID"].nunique())
        if not n_donors or n_obs / n_donors < PSEUDOREPLICATION_RATIO:
            return df, False, n_obs, n_donors

        keys = ["DonorID"] + [c for c in group_cols if c in df.columns]
        collapsed = (df.groupby(keys, observed=True)["expression"]
                     .mean().reset_index())
        return collapsed, True, n_obs, n_donors

    def _diagnosis_column(self) -> str:
        if "Diagnosis" not in self.meta.columns:
            raise ValueError(
                f"{self.dataset_id} has no Diagnosis column, so it cannot "
                "support a case/control comparison. Datasets that can: "
                "PsychENCODE (control, schizophrenia, bipolar, ASD, affective), "
                "BrainSeq (control, schizophrenia), Velmeshev (ASD, control). "
                "The prenatal sets (HDBR, BrainSpan, Cameron) are "
                "neurotypical throughout, so there is no case group to "
                "compare against."
            )
        return "Diagnosis"

    def compare_by_diagnosis(self, gene: str, reference: str = "Control") -> dict:
        """
        Case/control comparison for one gene, tested on the right sample size.

        Every non-reference diagnosis is compared with `reference` by Welch's
        t-test on donor means. The effect size, the group ns and the
        pseudoreplication state travel with the result, because the p-value
        alone is misleading on this data — see MIN_GROUP_N and
        PSEUDOREPLICATION_RATIO above.
        """
        column = self._diagnosis_column()
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)
        df = df.dropna(subset=[column, "expression"])

        levels = list(df[column].dropna().unique())
        if len(levels) < 2:
            raise ValueError(
                f"{self.dataset_id} has only one Diagnosis level "
                f"({levels[0] if levels else 'none'}), so there is nothing to "
                "compare. A case/control test needs at least two groups."
            )

        # Match the reference case-insensitively; freezes have used both
        # "Control" and "control".
        want = str(reference).strip().lower()
        matched = [lv for lv in levels if str(lv).strip().lower() == want]
        if not matched:
            raise ValueError(
                f"'{reference}' is not a Diagnosis level in {self.dataset_id}. "
                f"Available: {', '.join(map(str, levels))}."
            )
        ref = matched[0]

        frame, aggregated, n_obs, n_donors = self._donor_aggregate(df, [column])
        ref_values = frame[frame[column] == ref]["expression"]

        group_sizes = {str(lv): int((frame[column] == lv).sum()) for lv in levels}
        rows = []
        for lv in levels:
            if lv == ref:
                continue
            case = frame[frame[column] == lv]["expression"]
            stats_out = _welch(case, ref_values)
            rows.append({
                "diagnosis": str(lv),
                "mean": round(float(case.mean()), 3),
                "reference_mean": round(float(ref_values.mean()), 3),
                "delta": round(float(case.mean() - ref_values.mean()), 3),
                "n": int(len(case)),
                "reference_n": int(len(ref_values)),
                **stats_out,
            })

        rows.sort(key=lambda r: -abs(r["delta"]))
        note = make_statistical_note(
            n_observations=n_obs, n_donors=n_donors,
            unit_of_analysis="donor" if aggregated else "sample",
            group_sizes=group_sizes, aggregated=aggregated,
        )

        def _fmt_p(p):
            return None if p is None else (f"{p:.2e}" if p < 0.001 else f"{p:.3f}")

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "dataset": self.dataset_id,
            "unit": self.unit,
            "reference": str(ref),
            "comparisons": rows,
            "statistical_note": note,
            "table": make_table(
                title=(f"{symbol} — expression by diagnosis vs {ref} "
                       f"({self.dataset_id})"),
                columns=[
                    {"key": "diagnosis", "label": "Diagnosis"},
                    {"key": "n", "label": "n", "align": "right"},
                    {"key": "mean", "label": f"Mean {self.unit}",
                     "align": "right", "format": "2dp"},
                    {"key": "delta", "label": "vs reference",
                     "align": "right", "format": "2dp"},
                    {"key": "cohens_d", "label": "Cohen's d",
                     "align": "right", "format": "2dp"},
                    {"key": "p_display", "label": "p", "align": "right"},
                ],
                rows=[{**r, "p_display": _fmt_p(r["p"])} for r in rows],
                footnote=(
                    f"Welch's t-test against {ref} (n={len(ref_values)}), "
                    f"{'donor means' if aggregated else 'per-sample values'}. "
                    + note["text"]
                ),
            ),
            "note": (
                f"Case/control comparison in {self.dataset_id} ({self.unit}). "
                "You MUST report the group n alongside any difference, and you "
                "MUST state the caveat in statistical_note.text — it is not "
                "optional garnish. A small-n group with a large effect size is "
                "the most common way this result misleads. Render 'table' "
                "rather than retyping the numbers. This is an observational "
                "difference between diagnosis groups, not evidence of cause."
            ),
        }

    def compare_cell_type_by_diagnosis(self, gene: str,
                                       reference: str = "Control",
                                       resolution: str = "MajorCellType") -> dict:
        """
        Which cell type carries a case/control difference.

        Velmeshev pairs cell-type labels with ASD/control status, which is the
        dataset's reason for existing and the one question neither
        get_cell_type_expression nor compare_by_diagnosis can answer alone.
        Aggregated to donor x cell type before testing.
        """
        levels = self.cell_type_levels()
        if not levels:
            raise ValueError(
                f"{self.dataset_id} has no cell-type annotation, so a "
                "cell-type-by-diagnosis breakdown is not possible. Velmeshev "
                "is the dataset that pairs cell types with diagnosis."
            )
        column = self._diagnosis_column()
        key = METADATA_COLUMNS.get(str(resolution).strip(), str(resolution).strip())
        if key not in levels:
            raise ValueError(
                f"'{resolution}' is not a cell-type grouping in "
                f"{self.dataset_id}. Available: {', '.join(levels)}."
            )

        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)
        df = df.dropna(subset=[column, key, "expression"])

        dx_levels = list(df[column].dropna().unique())
        want = str(reference).strip().lower()
        matched = [lv for lv in dx_levels if str(lv).strip().lower() == want]
        if not matched:
            raise ValueError(
                f"'{reference}' is not a Diagnosis level in {self.dataset_id}. "
                f"Available: {', '.join(map(str, dx_levels))}."
            )
        ref = matched[0]
        cases = [lv for lv in dx_levels if lv != ref]
        if not cases:
            raise ValueError(
                f"{self.dataset_id} has only the {ref} group; nothing to compare."
            )
        case = cases[0]
        if len(cases) > 1:
            case = sorted(cases, key=lambda lv: -int((df[column] == lv).sum()))[0]

        frame, aggregated, n_obs, n_donors = self._donor_aggregate(df, [column, key])

        rows = []
        for ct in frame[key].dropna().unique():
            sub = frame[frame[key] == ct]
            a = sub[sub[column] == case]["expression"]
            b = sub[sub[column] == ref]["expression"]
            if len(a) < 2 or len(b) < 2:
                continue
            stats_out = _welch(a, b)
            rows.append({
                "cell_type": str(ct),
                "case_mean": round(float(a.mean()), 3),
                "reference_mean": round(float(b.mean()), 3),
                "delta": round(float(a.mean() - b.mean()), 3),
                "n_case_donors": int(len(a)),
                "n_reference_donors": int(len(b)),
                **stats_out,
            })
        if not rows:
            raise ValueError(
                f"No {key} level in {self.dataset_id} has at least 2 donors in "
                f"both {case} and {ref}, so no cell-type test can be run."
            )

        rows.sort(key=lambda r: r["delta"])
        largest = max(rows, key=lambda r: abs(r["delta"]))
        note = make_statistical_note(
            n_observations=n_obs, n_donors=n_donors,
            unit_of_analysis="donor x cell type" if aggregated else "observation",
            aggregated=aggregated,
            extra=[
                f"{len(rows)} cell types were each tested; with no multiple-"
                f"comparison correction applied, a single nominally significant "
                f"cell type among {len(rows)} is weak evidence on its own."
            ],
        )

        def _fmt_p(p):
            return None if p is None else (f"{p:.2e}" if p < 0.001 else f"{p:.3f}")

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "dataset": self.dataset_id,
            "unit": self.unit,
            "case": str(case), "reference": str(ref),
            "resolution": key,
            "by_cell_type": rows,
            "largest_difference": {"cell_type": largest["cell_type"],
                                   "delta": largest["delta"], "p": largest["p"]},
            "statistical_note": note,
            "table": make_table(
                title=(f"{symbol} — {case} vs {ref} by {key} "
                       f"({self.dataset_id})"),
                columns=[
                    {"key": "cell_type", "label": "Cell type"},
                    {"key": "case_mean", "label": f"{case}", "align": "right",
                     "format": "2dp"},
                    {"key": "reference_mean", "label": f"{ref}",
                     "align": "right", "format": "2dp"},
                    {"key": "delta", "label": "Difference", "align": "right",
                     "format": "2dp"},
                    {"key": "n_case_donors", "label": "Donors",
                     "align": "right"},
                    {"key": "p_display", "label": "p", "align": "right"},
                ],
                rows=[{**r, "p_display": _fmt_p(r["p"])} for r in rows],
                footnote=(
                    f"Welch's t-test per cell type on donor means. " + note["text"]
                ),
            ),
            "note": (
                f"Cell-type-resolved {case} vs {ref} in {self.dataset_id}. "
                "Report the donor n and the multiple-testing caveat from "
                "statistical_note.text. Name the cell type with the largest "
                "difference from 'largest_difference' — do NOT scan the rows "
                "and pick one yourself. Render 'table'."
            ),
        }

    def get_developmental_trajectory(self, gene: str) -> dict:
        """
        Mean expression per age interval, plus the transitions ranked by size.

        The ranking is computed here on purpose: asking a model to eyeball
        "where does it rise fastest" from a list of means invites a confident
        wrong answer. Steepest-change claims must come from this field.
        """
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        means = df.groupby("AgeInterval")["expression"].mean()
        ordered = [a for a in AGE_INTERVAL_ORDER if a in means.index]
        series = [{"age_interval": a, "mean": round(float(means[a]), 3),
                   "n": int((df["AgeInterval"] == a).sum())} for a in ordered]

        deltas = [
            {
                "from": ordered[i],
                "to": ordered[i + 1],
                "delta": round(float(means[ordered[i + 1]] - means[ordered[i]]), 3),
                "spans_birth": (
                    AGE_INTERVAL_ORDER.index(ordered[i]) < _FIRST_POSTNATAL_INDEX
                    <= AGE_INTERVAL_ORDER.index(ordered[i + 1])
                ),
            }
            for i in range(len(ordered) - 1)
        ]
        by_size = sorted(deltas, key=lambda d: abs(d["delta"]), reverse=True)
        peak = max(series, key=lambda p: p["mean"]) if series else None

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "unit": "log2(RPKM+1)",
            "trajectory": series,
            "peak": peak,
            "steepest_transition": by_size[0] if by_size else None,
            "transitions_by_magnitude": by_size[:5],
            "table": make_table(
                title=f"{symbol} — mean expression by age interval",
                columns=[
                    {"key": "age_interval", "label": "Age Interval"},
                    {"key": "mean", "label": "Mean Expression", "align": "right",
                     "format": "2dp"},
                    {"key": "n", "label": "n", "align": "right"},
                ],
                rows=series,
                highlight_row=(
                    next((i for i, p in enumerate(series) if p is peak), None)
                ),
                highlight_note="peak",
                footnote=f"log2(RPKM+1), {len(df)} BrainSpan samples.",
            ),
            "note": (
                "steepest_transition and peak are computed from the data. Do not "
                "infer the largest change or the maximum from the trajectory list "
                "by inspection — quote these fields. Render 'table' rather than "
                "retyping the numbers into prose."
            ),
        }

    def get_variance_partition(self, gene: str, cell_type_controlled: bool = False) -> dict:
        """
        Variance decomposition for a gene, with the technical share pre-computed.

        cell_type_controlled=True uses the model that includes cell-type
        fractions as covariates.
        """
        ensembl = self._resolve_gene(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)
        source = self.vp_decon if cell_type_controlled else self.vp

        if ensembl not in source.index:
            raise ValueError(
                f"Gene '{gene}' ({ensembl}) has no variance partition result. "
                "varPart was run on expressed genes only."
            )

        row = source.loc[ensembl]
        components = {k: round(float(v), 4) for k, v in row.items()}
        technical = {k: v for k, v in components.items() if k in TECHNICAL_COMPONENTS}
        ranked = sorted(
            ((k, v) for k, v in components.items() if k != "Residuals"),
            key=lambda kv: kv[1], reverse=True,
        )

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "model": "cell_type_controlled" if cell_type_controlled else "standard",
            "variance_components": components,
            "ranked_components": [{"component": k, "fraction": v} for k, v in ranked],
            "top_component": (
                {"component": ranked[0][0], "fraction": ranked[0][1]} if ranked else None
            ),
            "technical_total": round(sum(technical.values()), 4),
            "technical_breakdown": technical,
            "residual": components.get("Residuals"),
            # A proportion bar rather than a table: variance decomposition is a
            # part-of-whole result, and the finding is usually "one covariate
            # dominates" — visible instantly in a bar, arithmetic in a table.
            "table": make_stacked_bar(
                title=(
                    f"Variance decomposition · "
                    f"{'cell-type controlled' if cell_type_controlled else 'standard'} · "
                    f"{self.dataset_id}"
                ),
                subtitle=symbol,
                segments=[{"label": k, "fraction": v} for k, v in ranked
                          if k != "Residuals"]
                         + [{"label": "Residuals",
                             "fraction": components.get("Residuals") or 0}],
                footnote=_technical_footnote(technical),
            ),
            "note": (
                "Fractions of total expression variance explained; they sum to 1. "
                "Technical covariates are RIN, PMI, pH and dissection score. "
                "The bar is rendered for the user automatically — do NOT list "
                "these components in prose. Name only the dominant driver and "
                "the technical total, in one or two sentences."
            ),
        }

    def correlate_with_covariate(self, gene: str, covariate: str = None) -> dict:
        """
        Does this gene's expression track a technical covariate?

        get_variance_partition reports the technical *share* but cannot say
        which covariate or in which direction. That matters because a regional
        or diagnostic difference in a dataset where expression tracks RIN at
        rho=+0.25 (GTEx SHANK3, p=4.8e-40) may be a tissue-quality difference.
        With no `covariate` named, every numeric covariate is tested and ranked
        by |rho|, which is the more useful default: the question is usually
        "is anything technical driving this" rather than a named suspicion.
        """
        from scipy import stats
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        # Sample-level covariates only. AgeNumeric is biology, not QC, but it
        # belongs here too — a confound is a confound whichever kind it is.
        skip = {"expression", "SampleID"} | set(CELL_TYPE_COLUMNS)
        numeric = [c for c in df.columns
                   if c not in skip and df[c].dtype.kind in "fi"
                   and df[c].notna().sum() >= MIN_GROUP_N]
        if not numeric:
            raise ValueError(
                f"{self.dataset_id} has no numeric sample covariates with at "
                f"least {MIN_GROUP_N} values, so no correlation can be "
                "computed. describe_metadata lists what it does record."
            )

        if covariate is not None:
            key = METADATA_COLUMNS.get(str(covariate).strip(), str(covariate).strip())
            match = [c for c in numeric if c.lower() == key.lower()]
            if not match:
                match = [c for c in numeric if key.lower() in c.lower()]
            if not match:
                raise ValueError(
                    f"'{covariate}' is not a numeric covariate in "
                    f"{self.dataset_id}. Available: {', '.join(numeric)}."
                )
            numeric = [match[0]]

        rows = []
        for col in numeric:
            sub = df[[col, "expression"]].dropna()
            if len(sub) < MIN_GROUP_N:
                continue
            # A constant covariate has no defined correlation — GTEx records
            # "Duplication Rate Mapped" with one value for all 2,642 samples.
            # Skipped here rather than letting scipy warn and return NaN, so
            # the console stays quiet and the reason is stated.
            if sub[col].nunique() < 2:
                continue
            # Spearman: RIN and dissection score are ordinal-ish and the
            # relationship need not be linear.
            rho, p = stats.spearmanr(sub[col], sub["expression"])
            if np.isnan(rho):
                continue
            rows.append({
                "covariate": col,
                "rho": round(float(rho), 3),
                "p": float(p),
                "n": int(len(sub)),
                "technical": col in TECHNICAL_COMPONENTS,
            })
        if not rows:
            raise ValueError(
                f"No covariate in {self.dataset_id} had enough paired values "
                f"with '{symbol}' to correlate."
            )

        rows.sort(key=lambda r: -abs(r["rho"]))
        strongest = rows[0]

        # The threshold below which a correlation is not worth warning about is
        # a judgement call; 0.2 is where a covariate starts being a plausible
        # alternative explanation for a modest group difference.
        warn = None
        if abs(strongest["rho"]) >= 0.2 and strongest["p"] < 0.05:
            warn = (
                f"{symbol} expression correlates with {strongest['covariate']} "
                f"in {self.dataset_id} (rho={strongest['rho']:+.3f}, "
                f"p={strongest['p']:.1e}, n={strongest['n']:,}). Any regional, "
                f"developmental or diagnostic difference reported for this gene "
                f"in this dataset could partly reflect "
                f"{strongest['covariate']} rather than biology."
            )

        def _fmt_p(p):
            return f"{p:.2e}" if p < 0.001 else f"{p:.3f}"

        return {
            "gene": symbol,
            "ensembl_id": ensembl,
            "dataset": self.dataset_id,
            "unit": self.unit,
            "n_covariates_tested": len(rows),
            "strongest": strongest,
            "correlations": rows,
            "statistical_note": make_statistical_note(
                n_observations=int(len(df)),
                n_donors=(int(df["DonorID"].nunique())
                          if "DonorID" in df.columns else None),
                unit_of_analysis="sample",
                covariate_warning=warn,
                extra=([f"{len(rows)} covariates tested without multiple-"
                        f"comparison correction."] if len(rows) > 1 else None),
            ),
            "table": make_table(
                title=(f"{symbol} — correlation with sample covariates "
                       f"({self.dataset_id})"),
                columns=[
                    {"key": "covariate", "label": "Covariate"},
                    {"key": "rho", "label": "Spearman rho", "align": "right",
                     "format": "2dp"},
                    {"key": "p_display", "label": "p", "align": "right"},
                    {"key": "n", "label": "n", "align": "right"},
                    {"key": "kind", "label": "Type"},
                ],
                rows=[{**r, "p_display": _fmt_p(r["p"]),
                       "kind": "technical" if r["technical"] else "biological"}
                      for r in rows],
                footnote=(
                    "Spearman rank correlation on sample-level values. "
                    "'technical' marks QC covariates (RIN, PMI, pH, dissection "
                    "score) — a strong correlation there means the expression "
                    "signal may be tissue quality."
                ),
            ),
            "note": (
                f"Covariate correlations in {self.dataset_id}. A correlation is "
                "not causation and not evidence of an artefact by itself, but a "
                "strong technical correlation is a reason to qualify any group "
                "difference you report for this gene. If statistical_note "
                "carries a covariate warning, state it. Render 'table'."
            ),
        }

    def correlate_genes(self, gene: str, other_gene: str) -> dict:
        """
        Co-expression of two genes across this dataset's samples.

        Correlation across samples, so a high value means the two genes move
        together across development/region/donor — not that they interact.
        """
        from scipy import stats
        ens_a, df_a = self._expression_frame(gene)
        ens_b, df_b = self._expression_frame(other_gene)
        sym_a = self.ensembl_to_symbol.get(ens_a, gene)
        sym_b = self.ensembl_to_symbol.get(ens_b, other_gene)
        if ens_a == ens_b:
            raise ValueError(
                f"'{gene}' and '{other_gene}' resolve to the same gene "
                f"({sym_a}); correlating a gene with itself gives rho=1.0."
            )

        joined = pd.DataFrame({
            "a": df_a["expression"].to_numpy(),
            "b": df_b["expression"].to_numpy(),
        }).dropna()
        if len(joined) < MIN_GROUP_N:
            raise ValueError(
                f"Only {len(joined)} {self.dataset_id} samples have values for "
                f"both {sym_a} and {sym_b} — too few to correlate."
            )

        rho, p_s = stats.spearmanr(joined["a"], joined["b"])
        r, p_p = stats.pearsonr(joined["a"], joined["b"])
        n_donors = (int(df_a["DonorID"].nunique())
                    if "DonorID" in df_a.columns else None)

        return {
            "gene": sym_a, "other_gene": sym_b,
            "ensembl_ids": [ens_a, ens_b],
            "dataset": self.dataset_id,
            "unit": self.unit,
            "n": int(len(joined)),
            "spearman_rho": round(float(rho), 3), "spearman_p": float(p_s),
            "pearson_r": round(float(r), 3), "pearson_p": float(p_p),
            "direction": ("positive" if rho > 0 else
                          "negative" if rho < 0 else "none"),
            "statistical_note": make_statistical_note(
                n_observations=int(len(joined)), n_donors=n_donors,
                unit_of_analysis="sample",
                extra=[
                    "Correlation across samples reflects shared variation with "
                    "development, region and donor — the dominant axes in this "
                    "data — so a strong value is not evidence of a specific "
                    "regulatory relationship."
                ],
            ),
            "note": (
                f"Co-expression of {sym_a} and {sym_b} across "
                f"{len(joined):,} {self.dataset_id} samples "
                f"(rho={rho:+.3f}). Report rho, n and the caveat from "
                "statistical_note.text. Two numbers do not need a table."
            ),
        }

    def get_cell_type_composition(self, group_by: str = None) -> dict:
        """
        MultiBrain deconvolution proportions as a part-of-whole composition.

        The five bulk datasets carry per-sample estimated proportions of
        neurons, astrocytes, microglia, oligodendrocytes and endothelia, and
        they sum to exactly 1.0 — a genuine composition rather than five
        independent numbers, so it belongs in a stacked bar, not a table.

        This is cellular *makeup of the tissue*, independent of any gene, and
        is what "cell-type signal" means in bulk data. Not to be confused with
        get_cell_type_expression, which is per-nucleus expression in the
        single-nucleus sets.
        """
        have = [c for c in CELL_TYPE_COLUMNS if c in self.meta.columns]
        if not have:
            raise ValueError(
                f"{self.dataset_id} has no MultiBrain deconvolution "
                "proportions. These exist for the bulk datasets only "
                "(BrainSpan, BrainSeq, HDBR, GTEx, PsychENCODE) — a "
                "single-nucleus dataset needs no deconvolution because each "
                "nucleus already carries a cell-type label; use "
                "get_cell_type_expression there."
            )

        df = self.meta[have + (["DonorID"] if "DonorID" in self.meta.columns
                               else [])].copy()
        strata = None
        if group_by:
            key = METADATA_COLUMNS.get(str(group_by).strip(), str(group_by).strip())
            if key not in self.meta.columns:
                raise ValueError(
                    f"'{group_by}' is not a column in {self.dataset_id}. "
                    "describe_metadata lists what it records."
                )
            df[key] = self.meta[key]
            strata = key
        df = df.dropna(subset=have)
        if df.empty:
            raise ValueError(
                f"No {self.dataset_id} samples have complete deconvolution "
                "proportions."
            )

        def _composition(sub):
            means = sub[have].mean()
            total = float(means.sum())
            # Renormalise: per-sample rows sum to 1, but means over a subset
            # with different missingness need not.
            return {c: float(means[c] / total) for c in have}, int(len(sub))

        overall, n_overall = _composition(df)
        segments = [
            {"label": c, "fraction": overall[c],
             "color": VARIANCE_COLORS.get(c, "#9ca3af")}
            for c in sorted(have, key=lambda c: -overall[c])
        ]

        by_stratum = []
        if strata:
            order = self._levels(df, strata)
            for lv in order:
                sub = df[df[strata] == lv]
                if sub.empty:
                    continue
                comp, n = _composition(sub)
                by_stratum.append({"stratum": str(lv), "n": n, **{
                    k: round(v, 4) for k, v in comp.items()}})

        dominant = segments[0]
        title = f"Cell-type composition — {self.dataset_id}"
        if strata:
            title += f" (mean over {n_overall} samples, also split by {strata})"

        return {
            "dataset": self.dataset_id,
            "n_samples": n_overall,
            "cell_types": have,
            "composition": {k: round(v, 4) for k, v in overall.items()},
            "dominant": {"cell_type": dominant["label"],
                         "fraction": round(dominant["fraction"], 4)},
            "grouped_by": strata,
            "by_stratum": by_stratum,
            # Under "table" rather than "stacked_bar": that is the key the
            # agent loop collects renderables from, and the frontend
            # discriminates on the payload's own "type" field. Same convention
            # get_variance_partition uses for its proportion bar.
            "table": make_stacked_bar(
                title=title,
                segments=segments,
                subtitle=(f"MultiBrain deconvolution, mean of {n_overall} "
                          f"samples"),
                footnote=(
                    "Estimated proportions from the MultiBrain signature "
                    "matrix, not measured cell counts. Per-sample proportions "
                    "sum to 1; these are the sample means, renormalised."
                ),
            ),
            "statistical_note": make_statistical_note(
                n_observations=n_overall,
                n_donors=(int(df["DonorID"].nunique())
                          if "DonorID" in df.columns else None),
                unit_of_analysis="sample",
                extra=[
                    "Deconvolution estimates depend on the signature matrix "
                    "and are not measured cell counts; compare them across "
                    "strata within a dataset rather than across datasets."
                ],
            ),
            "note": (
                f"Cell-type composition of {self.dataset_id} tissue from "
                "MultiBrain deconvolution. This is the tissue's cellular "
                "makeup, not any gene's expression. A stacked proportion bar "
                "is returned in 'table' with every percentage in its "
                "legend — keep your text to one or two sentences naming the "
                "dominant type and do not enumerate the rest."
            ),
        }

    def get_dataset_metadata(self) -> dict:
        """
        Summary of one dataset.

        Every field is conditional on the column existing. The eight published
        datasets do NOT share a schema — BrainSpan has 18 metadata columns,
        GTEx 48, Cameron 6, and only some carry Period, AgeNumeric or
        StructureAcronym. Reading them unconditionally raised KeyError on five
        of the eight, which surfaced to the user as "Missing required argument:
        'AgeNumeric'" rather than a dataset summary.
        """
        entry = next((e for e in DATASET_CATALOG if e["id"] == self.dataset_id), {})
        columns = set(self.meta.columns)

        summary = {
            "dataset": self.dataset_id,
            "assay": entry.get("assay", "bulk RNA-seq, post-mortem human brain"),
            "description": entry.get("description", ""),
            "n_samples": int(len(self.meta)),
            "n_samples_joinable": len(self.shared_samples),
            "n_genes": int(len(self.expr)),
            "unit": f"log2({entry.get('unit', 'RPKM')}+1)",
            "metadata_columns": sorted(columns - {"SampleID"}),
        }

        for field, column in (("regions", "Regions"),
                              ("structures", "StructureAcronym"),
                              ("periods", "Period")):
            if column in columns:
                summary[field] = self.meta[column].value_counts().to_dict()

        if self.age_intervals:
            summary["age_intervals"] = self.age_intervals

        if "AgeNumeric" in columns:
            ages = pd.to_numeric(self.meta["AgeNumeric"], errors="coerce").dropna()
            if not ages.empty:
                summary["age_range_numeric"] = {"min": float(ages.min()),
                                                "max": float(ages.max())}

        present_cell_types = [c for c in CELL_TYPE_COLUMNS if c in columns]
        if present_cell_types:
            summary["cell_type_fractions_available"] = present_cell_types

        covariates = {}
        if getattr(self, "vp", None) is not None and len(self.vp.columns):
            covariates["standard"] = list(self.vp.columns)
        if getattr(self, "vp_decon", None) is not None and len(self.vp_decon.columns):
            covariates["cell_type_controlled"] = list(self.vp_decon.columns)
        if covariates:
            summary["variance_partition_covariates"] = covariates
        else:
            summary["variance_partition_available"] = False

        return summary

    def describe_metadata(self, variable: str | None = None) -> dict:
        """
        Profile the sample metadata: what columns exist, their type, range or
        categories, and how complete they are.

        Missingness is reported prominently because it is load-bearing here —
        RIN, PMI and dissection score are absent for 157 of 524 BrainSpan
        samples and pH for 221, so any covariate analysis silently runs on a
        subset. An answer about this dataset that omits that is misleading.
        """
        if variable is not None:
            key = METADATA_COLUMNS.get(variable.strip(), variable.strip())
            if key not in self.meta.columns:
                raise ValueError(
                    f"'{variable}' is not a metadata column. Available: "
                    + ", ".join(sorted(self.meta.columns))
                )
            columns = [key]
        else:
            columns = [c for c in self.meta.columns if c != "SampleID"]

        n = len(self.meta)
        profile = {}
        for col in columns:
            series = self.meta[col]
            present = int(series.notna().sum())
            entry = {
                "n_present": present,
                "n_missing": int(n - present),
                "pct_complete": round(100 * present / n, 1),
            }
            if pd.api.types.is_numeric_dtype(series):
                clean = series.dropna()
                entry.update({
                    "type": "numeric",
                    "min": round(float(clean.min()), 3),
                    "max": round(float(clean.max()), 3),
                    "median": round(float(clean.median()), 3),
                    "mean": round(float(clean.mean()), 3),
                })
            else:
                counts = series.value_counts()
                entry.update({
                    "type": "categorical",
                    "n_categories": int(len(counts)),
                    "categories": {str(k): int(v) for k, v in counts.head(30).items()},
                })
                if col == "AgeInterval":
                    entry["developmental_order"] = self.age_intervals
            profile[col] = entry

        def _range(col, e):
            if e["type"] == "numeric":
                return f"{e['min']} – {e['max']} (median {e['median']})"
            cats = list(e["categories"])
            shown = ", ".join(cats[:4])
            return f"{e['n_categories']} levels: {shown}" + (" …" if len(cats) > 4 else "")

        result = {
            "dataset": self.dataset_id,
            "n_samples": n,
            "variables": profile,
            "table": make_table(
                title=(f"{self.dataset_id} — {variable}" if variable
                       else f"{self.dataset_id} sample metadata"),
                columns=[
                    {"key": "variable", "label": "Variable"},
                    {"key": "type", "label": "Type"},
                    {"key": "range", "label": "Range / categories"},
                    {"key": "complete", "label": "Complete", "align": "right"},
                ],
                rows=[
                    {"variable": col, "type": e["type"], "range": _range(col, e),
                     "complete": f"{e['n_present']}/{n}"}
                    for col, e in profile.items()
                ],
                footnote=f"{n} post-mortem samples.",
            ),
        }
        if variable is None:
            incomplete = {
                c: profile[c]["n_missing"] for c in profile if profile[c]["n_missing"]
            }
            result["incomplete_variables"] = dict(
                sorted(incomplete.items(), key=lambda kv: -kv[1])
            )
            result["note"] = (
                "Variables listed in incomplete_variables are missing for some "
                "samples — state this when reporting on them, since analyses "
                "using those covariates run on a reduced sample set."
            )
        return result

    #: Genomic annotation table, set by build_remote_brainspan_loader when the
    #: published bundle's /data group is available. The local CSV path has no
    #: coordinates, so it stays None and the locus tools refuse rather than
    #: guess.
    annotation = None
    gene_presence = None

    def _require_annotation(self):
        if self.annotation is None or "chr" not in self.annotation.columns:
            raise ValueError(
                "Genomic coordinates are not available on this data path. They "
                "come from the published bundle's annotation table; this "
                "instance is running from local CSVs, which carry gene symbols "
                "and names but no positions. Gene-symbol search still works "
                "via search_genes."
            )
        return self.annotation

    def find_genes_in_locus(self, chromosome: str, start: int, end: int,
                            limit: int = 100) -> dict:
        """
        Which genes lie in a genomic interval, and which datasets carry them.

        A user with a CNV or GWAS interval currently has to already know the
        gene names to ask anything. Overlap rather than containment: a gene
        straddling the boundary is in the interval for this purpose.
        """
        ann = self._require_annotation()
        chrom = str(chromosome).strip().upper().replace("CHR", "")
        start, end = int(start), int(end)
        if end < start:
            start, end = end, start

        rows_chr = ann[ann["chr"].astype(str).str.upper()
                       .str.replace("CHR", "", regex=False) == chrom]
        if rows_chr.empty:
            available = sorted(set(ann["chr"].astype(str)))[:30]
            raise ValueError(
                f"No genes annotated on chromosome '{chromosome}'. "
                f"Available: {', '.join(available)}."
            )

        hit = rows_chr[(rows_chr["start"] <= end) & (rows_chr["end"] >= start)]
        hit = hit.sort_values("start")
        total = int(len(hit))

        rows = []
        for _, r in hit.head(int(limit)).iterrows():
            entry = {
                "gene": str(r["symbol"]),
                "ensembl_id": str(r["ensembl_id"]),
                "chr": str(r["chr"]),
                "start": int(r["start"]),
                "end": int(r["end"]),
            }
            if self.gene_presence:
                entry["in_datasets"] = sorted(
                    ds for ds, idx in self.gene_presence.items()
                    if int(idx[r.name]) >= 0
                )
            rows.append(entry)

        return {
            "chr": chrom, "start": start, "end": end,
            "span_mb": round((end - start) / 1e6, 3),
            "n_genes": total,
            "returned": len(rows),
            "truncated": total > len(rows),
            "genes": rows,
            "table": make_table(
                title=f"Genes in chr{chrom}:{start:,}-{end:,}",
                columns=[
                    {"key": "gene", "label": "Gene"},
                    {"key": "start", "label": "Start", "align": "right"},
                    {"key": "end", "label": "End", "align": "right"},
                    {"key": "datasets_display", "label": "In datasets"},
                ],
                rows=[{**r, "datasets_display":
                       ", ".join(r.get("in_datasets", [])) or "—"} for r in rows],
                footnote=(
                    f"{total} gene(s) overlap the interval"
                    + (f"; first {len(rows)} shown." if total > len(rows) else ".")
                    + " Coordinates are hg38. 'In datasets' is which BITHub "
                    "datasets quantify the gene, from the bundle's annotation "
                    "index — not a claim about expression level."
                ),
            ),
            "note": (
                f"{total} annotated gene(s) overlap chr{chrom}:{start:,}-{end:,} "
                "(hg38). This is an annotation lookup, not an expression "
                "result — say nothing about expression levels unless you also "
                "call an expression tool. Render 'table'."
            ),
        }

    def gene_info(self, gene: str) -> dict:
        """
        Identity, coordinates and dataset coverage for one gene.

        The coverage part is the useful bit: which BITHub datasets quantify
        this gene is a fact the bundle knows, and without this tool the chat
        discovers a gene's absence only by a fetch failing mid-answer.
        """
        query = str(gene).strip()
        ensembl = self.symbol_to_ensembl.get(query.upper())
        if ensembl is None and query.upper().startswith("ENSG"):
            ensembl = query.split(".")[0]
        if ensembl is None or ensembl not in self.ensembl_to_symbol:
            near = self.search_genes(query, limit=5)
            raise ValueError(
                f"Gene '{gene}' not found in the BITHub annotation."
                + (f" Near matches: {', '.join(near)}." if near else "")
            )
        symbol = self.ensembl_to_symbol.get(ensembl, query)

        out = {"gene": symbol, "ensembl_id": ensembl}
        if self.annotation is not None:
            match = self.annotation[self.annotation["ensembl_id"] == ensembl]
            if not match.empty:
                r = match.iloc[0]
                for key in ("description", "chr", "start", "end"):
                    if key in match.columns and pd.notna(r[key]):
                        out[key] = (int(r[key]) if key in ("start", "end")
                                    else str(r[key]))
                if self.gene_presence:
                    present = sorted(ds for ds, idx in self.gene_presence.items()
                                     if int(idx[match.index[0]]) >= 0)
                    absent = sorted(set(self.gene_presence) - set(present))
                    out["in_datasets"] = present
                    out["absent_from"] = absent

        out["note"] = (
            f"Annotation for {symbol}. "
            + (f"Quantified in {len(out['in_datasets'])} of "
               f"{len(out['in_datasets']) + len(out['absent_from'])} datasets"
               + (f"; absent from {', '.join(out['absent_from'])}."
                  if out.get("absent_from") else ".")
               if "in_datasets" in out else
               "Dataset coverage is unavailable on this data path.")
            + " This is identity and coverage only — no expression values. "
            "If the user asked about a dataset this gene is absent from, say "
            "so before running an expression query that will fail."
        )
        return out

    def search_genes(self, query: str, limit: int = 10) -> list:
        """Symbol search, prefix matches first."""
        q = str(query).strip().upper()
        if not q:
            return []
        prefix = sorted(s for s in self.symbol_to_ensembl if s.startswith(q))
        contains = sorted(
            s for s in self.symbol_to_ensembl if q in s and not s.startswith(q)
        )
        return (prefix + contains)[:limit]

    # ── column helpers for the composable figures ─────────────────────────

    def _require_column(self, name, numeric=False, categorical=False) -> str:
        """Resolve a display or internal column name, checking it is plottable."""
        key = METADATA_COLUMNS.get(str(name).strip(), str(name).strip())
        if key not in self.meta.columns:
            raise ValueError(
                f"'{name}' is not a metadata column. Available: "
                + ", ".join(sorted(c for c in self.meta.columns if c != "SampleID"))
            )
        is_num = pd.api.types.is_numeric_dtype(self.meta[key])
        if numeric and not is_num:
            numeric_cols = [c for c in self.meta.columns
                            if pd.api.types.is_numeric_dtype(self.meta[c])]
            raise ValueError(
                f"'{key}' is categorical and cannot be a numeric axis. "
                f"Numeric columns: {', '.join(numeric_cols)}"
            )
        if categorical and is_num:
            raise ValueError(
                f"'{key}' is numeric and cannot be a colour or symbol encoding. "
                "Use a categorical column such as Regions, Period, Sex."
            )
        return key

    def _levels(self, df, col):
        """Category levels in a sensible order — developmental where applicable."""
        if col is None:
            return [None]
        values = df[col].dropna().unique().tolist()
        if col == "AgeInterval":
            return [a for a in AGE_INTERVAL_ORDER if a in values]
        if col == "Period":
            return [p for p in ("Prenatal", "Postnatal") if p in values]
        if col == "Regions":
            ordered = [r for r in ("Cortex", "Subcortex", "Cerebellum") if r in values]
            return ordered + sorted(set(values) - set(ordered))
        return sorted(values, key=str)

    # ── figure specs (Plotly, rendered client-side) ───────────────────────

    # BITHub primary palette, from frontend/src/lib/utils/colors.js
    #: Set by DatasetRegistry so payloads label themselves correctly. Defaults
    #: to BrainSpan for a loader constructed outside a registry.
    dataset_id = "BrainSpan"

    _PERIOD_COLORS = {"Prenatal": "#ebb6c7", "Postnatal": "#b94574"}

    def _level_color(self, column, level, index):
        """Period keeps its established two-tone pair so a box plot split by
        period matches the region figure; anything else cycles the palette."""
        if column == "Period":
            return self._PERIOD_COLORS.get(str(level), self._PRIMARY)
        return CATEGORICAL_COLORS[index % len(CATEGORICAL_COLORS)]
    _PRIMARY = "#cf648a"

    _BASE_LAYOUT = {
        "height": 360,
        "margin": {"t": 40, "b": 60, "l": 60, "r": 20},
        "font": {"size": 12},
        "paper_bgcolor": "rgba(0,0,0,0)",
        "plot_bgcolor": "rgba(0,0,0,0)",
    }

    @staticmethod
    def _axis(title: str, **extra) -> dict:
        return {
            "title": {"text": title},
            "automargin": True, "zeroline": False,
            "linecolor": "black", "linewidth": 1, "mirror": True,
            **extra,
        }

    def get_expression_figure(self, gene: str) -> dict:
        """Box plot of expression across Region x Period."""
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        regions = [r for r in ["Cortex", "Subcortex", "Cerebellum"]
                   if r in set(df["Regions"].dropna())]
        regions += sorted(set(df["Regions"].dropna()) - set(regions))
        periods = [p for p in ["Prenatal", "Postnatal"] if p in set(df["Period"])]

        traces = [{
            "type": "box",
            "name": period,
            "x": df.loc[df["Period"] == period, "Regions"].tolist(),
            "y": [round(v, 4) for v in df.loc[df["Period"] == period, "expression"]],
            "marker": {"color": self._PERIOD_COLORS.get(period, self._PRIMARY)},
            "boxmean": True,
        } for period in periods]

        return {
            "gene": symbol,
            "figure_type": "expression_box",
            "plotly_data": traces,
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "title": {"text": f"{symbol} expression — log2(RPKM+1)"},
                "xaxis": self._axis("Brain region",
                                    categoryorder="array", categoryarray=regions),
                "yaxis": self._axis("log2(RPKM+1)"),
                "boxmode": "group",
                "legend": {"orientation": "h", "y": 1.12, "x": 0},
            },
            "caption": (
                f"{symbol} log2(RPKM+1) across {len(df)} BrainSpan samples, "
                "grouped by region and developmental period."
            ),
        }

    def get_box_figure(self, gene: str, group_by: str = "AgeInterval",
                       split_by: str | None = None) -> dict:
        """
        Box plot of the per-sample distribution across any categorical column.

        The trajectory line shows means only, which hides the spread — a mean
        of 4.9 from tight replicates and one from a bimodal spread look
        identical. This shows the distribution behind each point, so an
        apparent developmental step can be checked against its variance.
        """
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        self._require_column(group_by, categorical=True)
        if split_by:
            self._require_column(split_by, categorical=True)

        order = self._levels(df, group_by)

        if split_by:
            traces = [{
                "type": "box",
                "name": str(level),
                "x": df.loc[df[split_by] == level, group_by].astype(str).tolist(),
                "y": [round(v, 4) for v in df.loc[df[split_by] == level, "expression"]],
                "marker": {"color": self._level_color(split_by, level, i)},
                "boxmean": True,
            } for i, level in enumerate(self._levels(df, split_by))]
        else:
            # One trace per group so each box can carry its own colour and the
            # sample count reaches the hover text.
            traces = []
            for i, level in enumerate(order):
                values = df.loc[df[group_by].astype(str) == str(level), "expression"]
                if values.empty:
                    continue
                traces.append({
                    "type": "box",
                    "name": str(level),
                    "y": [round(v, 4) for v in values],
                    "marker": {"color": self._level_color(group_by, level, i)},
                    "boxmean": True,
                    "showlegend": False,
                    "hovertemplate": (f"{level}<br>n={len(values)}"
                                      "<br>log2(RPKM+1) %{y:.2f}<extra></extra>"),
                })

        counts = df.groupby(group_by, observed=True)["expression"].size()
        thin = [str(k) for k, v in counts.items() if v < 5]

        return {
            "gene": symbol,
            "figure_type": "box",
            "plotly_data": traces,
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "title": {"text": f"{symbol} distribution by "
                                  f"{X_AXIS_LABELS.get(group_by, group_by)}"},
                "xaxis": self._axis(X_AXIS_LABELS.get(group_by, group_by),
                                   categoryorder="array",
                                   categoryarray=[str(o) for o in order]),
                "yaxis": self._axis("log2(RPKM+1)"),
                "boxmode": "group",
                **({"legend": {"orientation": "h", "y": 1.12, "x": 0}}
                   if split_by else {}),
            },
            "caption": (
                f"{symbol} log2(RPKM+1) distribution across {len(df)} samples, "
                f"grouped by {X_AXIS_LABELS.get(group_by, group_by).lower()}"
                + (f" and split by {X_AXIS_LABELS.get(split_by, split_by).lower()}"
                   if split_by else "")
                + ". Boxes show median, IQR and range; the dashed line is the mean."
                + (f" Groups with fewer than 5 samples: {', '.join(thin)}."
                   if thin else "")
            ),
        }

    def get_trajectory_figure(self, gene: str) -> dict:
        """Line plot of mean expression across ordered age intervals."""
        traj = self.get_developmental_trajectory(gene)
        symbol, points = traj["gene"], traj["trajectory"]
        xs = [p["age_interval"] for p in points]
        ys = [p["mean"] for p in points]

        shapes, annotations = [], []
        birth = next((i for i, a in enumerate(xs)
                      if AGE_INTERVAL_ORDER.index(a) >= _FIRST_POSTNATAL_INDEX), None)
        if birth not in (None, 0):
            shapes.append({"type": "line", "x0": birth - 0.5, "x1": birth - 0.5,
                           "yref": "paper", "y0": 0, "y1": 1,
                           "line": {"color": "#9ca3af", "width": 1, "dash": "dot"}})
            annotations.append({"x": birth - 0.5, "y": 1, "yref": "paper", "text": "birth",
                                "showarrow": False, "yshift": 8,
                                "font": {"size": 10, "color": "#6b7280"}})

        return {
            "gene": symbol,
            "figure_type": "developmental_trajectory",
            "plotly_data": [{
                "type": "scatter", "mode": "lines+markers", "x": xs, "y": ys,
                "name": symbol,
                "line": {"color": "#b94574", "width": 2.5, "shape": "spline"},
                "marker": {"size": 7, "color": self._PRIMARY,
                           "line": {"color": "#ffffff", "width": 1.5}},
            }],
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "title": {"text": f"{symbol} — mean expression by age interval"},
                "xaxis": self._axis("Age interval", tickangle=-45),
                "yaxis": self._axis("log2(RPKM+1)"),
                "shapes": shapes, "annotations": annotations, "showlegend": False,
            },
            "caption": (
                f"{symbol} mean log2(RPKM+1) across {len(xs)} BrainSpan age intervals."
            ),
        }

    def get_scatter_figure(self, gene, x="AgeNumeric", color_by="Regions",
                           symbol_by="Period", log_x=False) -> dict:
        """
        Expression against any numeric metadata variable, with categorical
        colour and symbol encodings.

        Generic on purpose: x, colour and symbol are chosen at call time, so
        "numeric age, shape by period, colour by region" and "RIN on x, colour
        by sex" are the same code path. Plotly needs one trace per
        colour x symbol combination for a legend that shows both encodings.
        """
        ensembl, df = self._expression_frame(gene)
        symbol = self.ensembl_to_symbol.get(ensembl, gene)

        xcol = self._require_column(x, numeric=True)
        ccol = self._require_column(color_by, categorical=True) if color_by else None
        scol = self._require_column(symbol_by, categorical=True) if symbol_by else None

        df = df.dropna(subset=[xcol])
        for col, role, cap in ((ccol, "colour", 12), (scol, "symbol", 6)):
            if col and df[col].nunique() > cap:
                raise ValueError(
                    f"'{col}' has {df[col].nunique()} levels — too many to "
                    f"encode as {role} (max {cap}). Try Regions, Period, Sex "
                    "or Hemisphere."
                )

        c_levels = self._levels(df, ccol)
        s_levels = self._levels(df, scol)

        traces = []
        for ci, c_val in enumerate(c_levels):
            for si, s_val in enumerate(s_levels):
                sub = df
                if ccol: sub = sub[sub[ccol] == c_val]
                if scol: sub = sub[sub[scol] == s_val]
                if sub.empty:
                    continue
                label = " · ".join(str(v) for v in (c_val, s_val) if v is not None)
                traces.append({
                    "type": "scatter", "mode": "markers",
                    "name": label or symbol,
                    "x": [round(float(v), 4) for v in sub[xcol]],
                    "y": [round(float(v), 4) for v in sub["expression"]],
                    "marker": {
                        "color": CATEGORICAL_COLORS[ci % len(CATEGORICAL_COLORS)],
                        "symbol": MARKER_SYMBOLS[si % len(MARKER_SYMBOLS)],
                        "size": 7, "opacity": 0.8,
                        "line": {"width": 0.5, "color": "#ffffff"},
                    },
                    "text": sub["SampleID"].tolist(),
                    "hovertemplate": (
                        f"%{{text}}<br>{xcol}: %{{x}}<br>log2(RPKM+1): %{{y:.2f}}"
                        f"<br>{label}<extra></extra>"
                    ),
                })

        xaxis = self._axis(X_AXIS_LABELS.get(xcol, xcol))
        if log_x:
            if (df[xcol] <= 0).any():
                raise ValueError(
                    f"'{xcol}' contains non-positive values (min "
                    f"{df[xcol].min():.3g}) so it cannot be log-scaled. "
                    "AgeNumeric is negative prenatally by design."
                )
            xaxis["type"] = "log"

        encoding = ", ".join(filter(None, [
            f"colour = {ccol}" if ccol else None,
            f"symbol = {scol}" if scol else None,
        ]))
        caption = (
            f"{symbol} log2(RPKM+1) against {X_AXIS_LABELS.get(xcol, xcol)} "
            f"across {len(df)} samples" + (f"; {encoding}." if encoding else ".")
        )
        if xcol == "AgeNumeric" and not log_x:
            caption += (
                " AgeNumeric is years relative to birth, so prenatal samples "
                "are negative and cluster near zero on a linear axis."
            )

        return {
            "gene": symbol,
            "figure_type": "scatter",
            "plotly_data": traces,
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "height": 420,
                "title": {"text": f"{symbol} — expression vs {X_AXIS_LABELS.get(xcol, xcol)}"},
                "xaxis": xaxis,
                "yaxis": self._axis("log2(RPKM+1)"),
                "legend": {"orientation": "v", "x": 1.02, "y": 1,
                           "font": {"size": 10}},
                "hovermode": "closest",
            },
            "caption": caption,
        }

    def get_heatmap_figure(self, genes, group_by="AgeInterval", scale="zscore") -> dict:
        """
        Genes x metadata-group mean expression.

        scale='zscore' centres and scales each gene across groups (the usual
        way an expression heatmap is read — it compares a gene to itself, not
        genes to each other). scale='raw' keeps log2(RPKM+1). The z-score
        colour scale reuses BITHub's own blue-white-red gradient.
        """
        if isinstance(genes, str):
            genes = [genes]
        if not genes:
            raise ValueError("Provide at least one gene symbol.")
        if len(genes) > MAX_HEATMAP_GENES:
            raise ValueError(
                f"{len(genes)} genes requested; the heatmap is capped at "
                f"{MAX_HEATMAP_GENES}. Narrow the list or ask for a table."
            )
        if scale not in ("zscore", "raw"):
            raise ValueError("scale must be 'zscore' or 'raw'.")

        gcol = self._require_column(group_by, categorical=True)

        resolved, missing, rows = [], [], []
        for g in genes:
            try:
                ensembl, df = self._expression_frame(g)
            except ValueError:
                missing.append(g)
                continue
            resolved.append(self.ensembl_to_symbol.get(ensembl, g))
            rows.append(df.groupby(gcol)["expression"].mean())

        if not resolved:
            raise ValueError(
                f"None of the requested genes were found: {', '.join(genes)}"
            )

        matrix = pd.DataFrame(rows, index=resolved)
        order = self._levels(pd.DataFrame({gcol: matrix.columns}), gcol)
        matrix = matrix[[c for c in order if c in matrix.columns]]

        if scale == "zscore":
            sd = matrix.std(axis=1).replace(0, np.nan)
            z = matrix.sub(matrix.mean(axis=1), axis=0).div(sd, axis=0)
            values, zmid, cbar = z.round(3), 0, "z-score"
            colorscale = [[0.0, GRADIENT_COLORS[0]], [0.5, GRADIENT_COLORS[1]],
                          [1.0, GRADIENT_COLORS[2]]]
            zmin, zmax = -2.5, 2.5
        else:
            values, zmid, cbar = matrix.round(3), None, "log2(RPKM+1)"
            colorscale = [[0.0, "#ffffff"], [1.0, GRADIENT_COLORS[2]]]
            zmin = zmax = None

        # Reverse rows so the first gene appears at the top of the plot.
        layout_extra = {"zmid": zmid} if zmid is not None else {}
        trace = {
            "type": "heatmap",
            "x": [str(c) for c in values.columns],
            "y": list(values.index)[::-1],
            "z": values.values[::-1].tolist(),
            "colorscale": colorscale,
            "colorbar": {"title": {"text": cbar, "side": "right"}, "thickness": 14},
            "hovertemplate": "%{y} · %{x}<br>%{z}<extra></extra>",
            **layout_extra,
        }
        if zmin is not None:
            trace["zmin"], trace["zmax"] = zmin, zmax

        return {
            "genes": resolved,
            "genes_not_found": missing,
            "figure_type": "heatmap",
            "plotly_data": [trace],
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "height": max(240, 46 + 26 * len(resolved)),
                "margin": {"t": 44, "b": 88, "l": 96, "r": 20},
                "title": {"text": (
                    f"Expression across {X_AXIS_LABELS.get(gcol, gcol)}"
                    f"{' (per-gene z-score)' if scale == 'zscore' else ''}")},
                "xaxis": self._axis("", tickangle=-45),
                "yaxis": self._axis(""),
            },
            "table": make_table(
                title=f"Mean expression by {X_AXIS_LABELS.get(gcol, gcol)}"
                      f"{' — z-scored per gene' if scale == 'zscore' else ''}",
                columns=[{"key": "gene", "label": "Gene"}] + [
                    {"key": str(c), "label": str(c), "align": "right", "format": "2dp"}
                    for c in values.columns
                ],
                rows=[{"gene": g, **{str(c): float(values.loc[g, c])
                                     if pd.notna(values.loc[g, c]) else None
                                     for c in values.columns}}
                      for g in values.index],
                footnote=(
                    f"{len(resolved)} genes"
                    + (f"; not found: {', '.join(missing)}" if missing else "")
                    + (". Z-scored per gene across groups." if scale == "zscore"
                       else ". log2(RPKM+1).")
                ),
            ),
            "caption": (
                f"{len(resolved)} genes across {len(values.columns)} "
                f"{X_AXIS_LABELS.get(gcol, gcol)} groups"
                + (", z-scored within each gene." if scale == "zscore"
                   else ", log2(RPKM+1).")
            ),
        }

    def get_variance_figure(self, gene: str, cell_type_controlled: bool = False) -> dict:
        """Bar chart of variance components, residuals excluded."""
        vp = self.get_variance_partition(gene, cell_type_controlled)
        ranked = vp["ranked_components"]
        symbol = vp["gene"]
        model = " (cell-type controlled)" if cell_type_controlled else ""

        return {
            "gene": symbol,
            "figure_type": "variance_partition",
            "plotly_data": [{
                "type": "bar",
                "x": [c["component"] for c in ranked],
                "y": [c["fraction"] for c in ranked],
                "marker": {"color": self._PRIMARY},
                "hovertemplate": "%{x}: %{y:.1%}<extra></extra>",
            }],
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "title": {"text": f"{symbol} — variance explained{model}"},
                "xaxis": self._axis("Covariate", tickangle=-40),
                "yaxis": self._axis("Fraction of variance", tickformat=".0%"),
                "showlegend": False,
            },
            "caption": (
                f"Variance in {symbol} expression explained by each covariate"
                f"{model}; residual variance ({vp['residual']:.1%}) omitted."
            ),
        }

    def get_composition_figure(self, group_by: str = None,
                               chart: str = "stacked_bar") -> dict:
        """
        Cell-type composition as a Plotly figure.

        Stacked bar by default, including when split by a stratum — a set of
        pie charts cannot be read comparatively, whereas stacked bars share a
        baseline and let the reader see a proportion change across development
        or region. A single pie is offered for the ungrouped case only, where
        there is nothing to compare against and a pie is a legitimate reading
        of one composition.
        """
        result = self.get_cell_type_composition(group_by=group_by)
        types = result["cell_types"]
        colors = [VARIANCE_COLORS.get(c, "#9ca3af") for c in types]

        if chart == "pie":
            if result["grouped_by"]:
                raise ValueError(
                    "A pie chart cannot show composition split by "
                    f"{result['grouped_by']} — one pie per stratum cannot be "
                    "compared by eye. Use chart='stacked_bar', which shares a "
                    "baseline across strata."
                )
            return {
                "figure_type": "composition_pie",
                "dataset": self.dataset_id,
                "plotly_data": [{
                    "type": "pie",
                    "labels": types,
                    "values": [result["composition"][c] for c in types],
                    "marker": {"colors": colors},
                    "sort": True,
                    "hole": 0.45,
                    "textinfo": "label+percent",
                    "hovertemplate": "%{label}: %{percent}<extra></extra>",
                }],
                "plotly_layout": {
                    **self._BASE_LAYOUT,
                    "title": {"text": (f"Cell-type composition — "
                                       f"{self.dataset_id}")},
                    "showlegend": False,
                },
                "caption": (
                    f"MultiBrain deconvolution, mean of {result['n_samples']} "
                    f"{self.dataset_id} samples. Estimated proportions, not "
                    "measured cell counts."
                ),
                "statistical_note": result["statistical_note"],
            }

        if not result["by_stratum"]:
            strata = [self.dataset_id]
            values = {c: [result["composition"][c]] for c in types}
            x_title = ""
        else:
            strata = [s["stratum"] for s in result["by_stratum"]]
            values = {c: [s[c] for s in result["by_stratum"]] for c in types}
            x_title = X_AXIS_LABELS.get(result["grouped_by"],
                                        result["grouped_by"])

        traces = [{
            "type": "bar",
            "name": c,
            "x": strata,
            "y": values[c],
            "marker": {"color": VARIANCE_COLORS.get(c, "#9ca3af")},
            "hovertemplate": f"{c}, %{{x}}: %{{y:.1%}}<extra></extra>",
        } for c in types]

        return {
            "figure_type": "composition",
            "dataset": self.dataset_id,
            "plotly_data": traces,
            "plotly_layout": {
                **self._BASE_LAYOUT,
                "barmode": "stack",
                "title": {"text": f"Cell-type composition — {self.dataset_id}"},
                "xaxis": self._axis(x_title, tickangle=-40 if x_title else 0),
                "yaxis": self._axis("Proportion of tissue", tickformat=".0%",
                                    range=[0, 1]),
                "showlegend": True,
                "legend": {"orientation": "h", "y": -0.35},
            },
            "caption": (
                f"MultiBrain deconvolution proportions across "
                f"{result['n_samples']} {self.dataset_id} samples"
                + (f", by {result['grouped_by']}" if result["grouped_by"] else "")
                + ". Estimated proportions, not measured cell counts."
            ),
            "statistical_note": result["statistical_note"],
        }


# ── Literature search (outside class, uses ToolUniverse) ──────────────────────

_tu = None


def get_tu():
    """
    Lazily build the ToolUniverse client.

    Imported here rather than at module scope for two reasons: importing
    tooluniverse pulls in fastmcp and loads a large tool registry (seconds),
    which every startup would otherwise pay for whether or not a literature
    question is ever asked; and it keeps a missing/broken optional dependency
    from taking down the whole service — search_literature returns an error
    payload instead.
    """
    global _tu
    if _tu is None:
        from tooluniverse import ToolUniverse  # noqa: PLC0415 — see docstring

        _tu = ToolUniverse()
        _tu.load_tools()
    return _tu


def search_literature(
    gene_symbol: str,
    context: str = "brain development expression",
    limit: int = 3,
) -> dict:
    """
    Search PubMed and EuropePMC for papers about a gene.
    Both APIs return {"status": "success", "data": [...]} — unwrap before iterating.
    """
    query = f"{gene_symbol} {context}"
    papers, errors = [], []

    try:
        tu = get_tu()
    except Exception as exc:
        # A broken optional dependency must be reported, not silently rendered
        # as "no papers found" — those mean very different things to a reader.
        return {
            "gene": gene_symbol,
            "query": query,
            "results": [],
            "papers": [],
            "total_found": 0,
            "error": (
                "Literature search is unavailable: ToolUniverse failed to load "
                f"({type(exc).__name__}: {exc}). Expression and variance tools "
                "are unaffected."
            ),
        }

    # ── PubMed ────────────────────────────────────────────────────────────────
    try:
        raw = tu.run({
            "name": "PubMed_search_articles",
            "arguments": {"query": query, "limit": limit},
        })
        # Unwrap envelope: {"status": "success", "data": [...]}
        results = raw.get("data", []) if isinstance(raw, dict) else raw
        if isinstance(results, list):
            for p in results:
                papers.append({
                    "source":      "PubMed",
                    "title":       p.get("title", ""),
                    "authors":     p.get("authors", [])[:3],
                    "year":        p.get("pub_year", p.get("year", "")),
                    "journal":     p.get("journal", ""),
                    "citations":   p.get("citations", None),
                    "doi":         p.get("doi", ""),
                    "url":         p.get("url", ""),
                    "open_access": p.get("open_access", None),
                })
    except Exception as e:
        errors.append(f"PubMed: {type(e).__name__}: {e}")

    # ── EuropePMC ─────────────────────────────────────────────────────────────
    try:
        raw = tu.run({
            "name": "EuropePMC_search_articles",
            "arguments": {"query": query, "limit": limit},
        })
        # Unwrap envelope: {"status": "success", "data": [...]}
        results = raw.get("data", []) if isinstance(raw, dict) else raw
        if isinstance(results, list):
            for p in results:
                papers.append({
                    "source":      "EuropePMC",
                    "title":       p.get("title", ""),
                    "authors":     p.get("authors", [])[:3],
                    "year":        p.get("year", ""),
                    "journal":     p.get("journal", ""),
                    "citations":   p.get("citations", None),
                    "doi":         p.get("doi", ""),
                    "url":         p.get("url", ""),
                    "open_access": p.get("open_access", None),
                })
    except Exception as e:
        errors.append(f"EuropePMC: {type(e).__name__}: {e}")

    # ── Deduplicate by title and cap total ────────────────────────────────────
    seen = set()
    unique = []
    for p in papers:
        key = p["title"].lower().strip()
        if key and key not in seen:
            seen.add(key)
            unique.append(p)

    hits = unique[:limit]
    return {
        "gene":        gene_symbol,
        "query":       query,
        # Both keys: the SvelteKit route reads `results`, the standalone page
        # reads `papers`. They were divergent, so citations rendered in one UI
        # and silently vanished in the other.
        "results":     hits,
        "papers":      hits,
        "total_found": len(unique),
        **({"errors": errors} if errors else {}),
        **({"error": "Both literature sources failed; see errors."}
           if errors and not hits else {}),
    }
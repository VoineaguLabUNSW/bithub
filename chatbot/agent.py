import json
import os
from dotenv import load_dotenv
from pathlib import Path
import anthropic
from data_loader import search_literature

load_dotenv(Path(__file__).parent / ".env")

# ── Tool definitions ──────────────────────────────────────────────────────────

#: `dataset` property, shared by every per-gene tool.
#:
#: dispatch_tool has always routed on args["dataset"], but most tools did not
#: DECLARE the parameter, so the model had no way to pass it and silently got
#: selection[0] — while the system prompt instructed it to name a dataset.
#: Defined once because eight datasets with three different units make the
#: guidance too long to duplicate correctly by hand.
_DATASET_PROPERTY = {
    "type": "string",
    "description": (
        "Which dataset to query: BrainSpan, BrainSeq, HDBR, GTEx, "
        "PsychENCODE (bulk tissue) or Cameron, HCA, Velmeshev "
        "(single-nucleus). Defaults to the first selected dataset. Pass it "
        "explicitly whenever the user names a dataset. Absolute expression "
        "values are NOT comparable between datasets — they are RPKM "
        "(BrainSpan, BrainSeq, HDBR), TPM (GTEx, PsychENCODE) or CPM "
        "(Cameron, HCA, Velmeshev) — so use compare_datasets, not two "
        "single-dataset calls, to compare across them."
    ),
}


def _with_dataset(schema: dict) -> dict:
    """Add the shared `dataset` property to a tool's input schema."""
    props = dict(schema.get("properties", {}))
    props["dataset"] = _DATASET_PROPERTY
    return {**schema, "properties": props}


TOOLS = [
    {
        "name": "get_expression",
        "description": (
            "Returns expression values for a gene across all BrainSpan samples, "
            "joined with sample metadata (brain region, developmental period, age, "
            "cell type fractions). Use this to answer questions about expression "
            "levels, developmental trajectories, or regional patterns."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {
                    "type": "string",
                    "description": "Gene symbol, e.g. SHANK3, MECP2, FOXP2",
                }
            },
            "required": ["gene"],
        },
    },
    {
        "name": "get_variance_partition",
        "description": (
            "Returns variance decomposition results for a gene, showing how much "
            "of the expression variance is explained by biological factors (Period, "
            "Regions, AgeNumeric, Sex, DonorID) vs technical factors (RIN, PMI, pH) "
            "vs residual noise. Use cell_type_controlled=true when the question is "
            "about expression independent of cell type composition."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {
                    "type": "string",
                    "description": "Gene symbol, e.g. SHANK3",
                },
                "cell_type_controlled": {
                    "type": "boolean",
                    "description": (
                        "If true, uses the model with cell type fractions as covariates. "
                        "Default false."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "get_dataset_metadata",
        "description": (
            "Returns a summary of one dataset: number of samples and genes, "
            "brain regions covered, developmental periods, age range, and available "
            "covariates. Use this to answer questions about the dataset itself."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "dataset": {
                    "type": "string",
                    "description": (
                        "Which dataset to summarise. Defaults to the first "
                        "selected dataset."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "compare_datasets",
        "description": (
            "Compare a gene's expression ACROSS datasets on the z-scored scale. "
            "Use whenever the user has selected more than one dataset, asks "
            "whether a finding holds up, replicates, or is corroborated "
            "elsewhere, or names two datasets. Returns one row per dataset plus "
            "an explicit list of any requested datasets that are not loaded. "
            "Datasets that could not be queried are reported, never silently "
            "dropped — if fewer than two datasets return data, "
            "comparison_possible is false and you must say the comparison could "
            "not be made."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"},
                "datasets": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Dataset ids to compare. Omit to use the user's current "
                        "selection."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "describe_metadata",
        "description": (
            "Profile the sample metadata: every variable, its type, its range "
            "(numeric) or categories with counts (categorical), and how many "
            "samples have a value. Use this for questions about what is IN the "
            "dataset — 'what metadata is available', 'what is the range of PMI', "
            "'which age intervals are covered', 'how many donors', 'is pH "
            "recorded'. Pass `variable` to profile one column, or omit it for "
            "the whole table. Returns a ready-to-render table plus an "
            "incomplete_variables summary."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "variable": {
                    "type": "string",
                    "description": (
                        "Optional single column, e.g. 'PMI', 'RIN', "
                        "'AgeInterval', 'Regions', 'DonorID'. Omit for all."
                    ),
                },
                "dataset": {
                    "type": "string",
                    "description": (
                        "Which dataset to profile, e.g. BrainSpan, BrainSeq, "
                        "GTEx, HDBR, PsychENCODE, Cameron, HCA, Velmeshev. "
                        "Defaults to the first selected dataset. Pass it "
                        "explicitly whenever the user names a dataset — the "
                        "metadata schemas differ substantially between them."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_genes",
        "description": "Search for gene symbols matching a query string. Use when unsure of exact symbol.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Partial or full gene symbol to search for",
                }
            },
            "required": ["query"],
        },
    },
    {
        "name": "get_developmental_trajectory",
        "description": (
            "Returns mean expression per age interval in developmental order, plus "
            "the transitions between consecutive intervals ranked by magnitude. "
            "REQUIRED before making any claim about where expression rises or falls "
            "fastest, when a change occurs, or how steep a trend is — quote the "
            "steepest_transition field rather than inferring it from the series."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"}
            },
            "required": ["gene"],
        },
    },
    {
        "name": "generate_figure",
        "description": (
            "Generate an inline Plotly figure. Use whenever a visual helps — "
            "especially on any request to show, plot, visualise or compare.\n"
            "figure_type:\n"
            "  'expression' — box plot across regions and periods (default)\n"
            "  'trajectory' — line plot of means across age intervals\n"
            "  'variance'   — variance-partition bar chart\n"
            "  'scatter'    — one point per sample: expression against any "
            "NUMERIC metadata column (x), with any CATEGORICAL columns encoded "
            "as colour (color_by) and marker shape (symbol_by). Use this for "
            "sample-level questions, continuous covariates, or any request "
            "combining two encodings, e.g. 'numeric age on x, colour by region, "
            "shape by period'.\n"
            "  'heatmap'    — genes x metadata groups, z-scored per gene by "
            "default. Use for comparing several genes at once; pass `genes`.\n"
            "  'composition' — STACKED BAR of the tissue's cell-type makeup "
            "from MultiBrain deconvolution (bulk datasets only). No `gene`; "
            "pass `group_by` to split by age interval, region or diagnosis and "
            "see composition shift across it.\n"
            "  'composition_pie' — the same composition as a single donut. "
            "Only valid WITHOUT `group_by`; prefer 'composition' otherwise, "
            "because separate pies cannot be compared by eye.\n"
            "Valid x / color_by / symbol_by / group_by values are metadata "
            "columns — call describe_metadata if unsure what exists."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {
                    "type": "string",
                    "description": "Gene symbol. Required for all types except heatmap.",
                },
                "genes": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Gene symbols for figure_type='heatmap' (max 60).",
                },
                "figure_type": {
                    "type": "string",
                    "enum": ["expression", "trajectory", "variance", "scatter",
                             "heatmap", "box", "composition", "composition_pie"],
                    "description": (
                        "Which figure to draw. Default 'expression'. Use 'box' to "
                        "show the DISTRIBUTION per group (median, IQR, range, mean) "
                        "rather than a line of means — prefer it whenever the "
                        "question is about spread, variability, overlap between "
                        "groups, or whether a difference is real given the scatter. "
                        "'trajectory' is a line of means and hides the spread."
                    ),
                },
                "x": {
                    "type": "string",
                    "description": (
                        "scatter only. Numeric metadata column for the x-axis, "
                        "e.g. AgeNumeric, RIN, PMI, pH, Neurons. Default AgeNumeric."
                    ),
                },
                "color_by": {
                    "type": "string",
                    "description": (
                        "scatter only. Categorical column for colour, e.g. "
                        "Regions, Period, Sex. Default Regions. Max 12 levels."
                    ),
                },
                "symbol_by": {
                    "type": "string",
                    "description": (
                        "scatter only. Categorical column for marker shape, "
                        "e.g. Period, Sex. Default Period. Max 6 levels."
                    ),
                },
                "group_by": {
                    "type": "string",
                    "description": (
                        "heatmap and box. Categorical column to group by — "
                        "heatmap columns, or one box per level. Default "
                        "AgeInterval."
                    ),
                },
                "split_by": {
                    "type": "string",
                    "description": (
                        "box only. Optional second categorical column; draws "
                        "grouped boxes, e.g. group_by=Regions split_by=Period."
                    ),
                },
                "scale": {
                    "type": "string",
                    "enum": ["zscore", "raw"],
                    "description": (
                        "heatmap only. 'zscore' (default) scales each gene "
                        "across groups; 'raw' shows log2(RPKM+1)."
                    ),
                },
                "cell_type_controlled": {
                    "type": "boolean",
                    "description": "variance only. Default false.",
                },
            },
            "required": [],
        },
    },
    {
        "name": "search_literature",
        "description": (
            "Search PubMed and EuropePMC for published papers about a gene "
            "in the context of brain development, neurodevelopmental disorders, "
            "or expression studies. Call this when the user asks what is known "
            "about a gene, wants references, or asks an interpretive question "
            "that would benefit from literature context. Do NOT call this on "
            "every expression query — only when literature context is relevant."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene_symbol": {
                    "type": "string",
                    "description": "Gene symbol e.g. MECP2, SHANK3",
                },
                "context": {
                    "type": "string",
                    "description": (
                        "Biological context for the search, e.g. "
                        "'brain development expression' or "
                        "'autism spectrum disorder neurodevelopment'. "
                        "Default: 'brain development expression'."
                    ),
                },
                "limit": {
                    "type": "integer",
                    "description": "How many papers to return, 1-10. Default 3.",
                },
            },
            "required": ["gene_symbol"],
        },
    },
    {
        "name": "get_cell_type_expression",
        "description": (
            "Mean expression per CELL TYPE, for the single-nucleus datasets "
            "(Cameron, HCA, Velmeshev). This is the axis those datasets are "
            "resolved on: they have cell-type labels per nucleus and no "
            "developmental period, so get_expression's region x period summary "
            "does not apply to them.\n"
            "REQUIRED for any question about which cell type expresses a gene, "
            "whether expression is neuronal or glial, or cell-type enrichment "
            "in these datasets — do not infer a cell type from a bulk "
            "dataset's regional pattern.\n"
            "Returns one row per cell type sorted by mean, plus "
            "'vs_dataset_mean' (difference from the gene's mean across all "
            "nuclei, in log2 units) and 'highest'. Quote 'highest' rather than "
            "scanning the rows.\n"
            "For BULK datasets this raises an error naming "
            "get_variance_partition instead, whose cell-type-proportion "
            "components are how cell-type signal appears in bulk tissue."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"},
                "cell_type": {
                    "type": "string",
                    "description": (
                        "Optional single cell type to highlight, e.g. "
                        "'Microglia', 'Excitatory Neurons', 'Astrocytes'. "
                        "Matched case-insensitively. Omit to get all cell "
                        "types. Level names differ between datasets — call "
                        "describe_metadata if a name is rejected."
                    ),
                },
                "resolution": {
                    "type": "string",
                    "description": (
                        "Which annotation column to group by. Default "
                        "'MajorCellType' (7-10 interpretable types) — keep it "
                        "unless the user asks for finer resolution. Other "
                        "columns exist on some datasets only ('Class', "
                        "'Subclass' on HCA; 'CellType' on Cameron and "
                        "Velmeshev, with 91-120 levels)."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "compare_by_diagnosis",
        "description": (
            "Compare a gene's expression between diagnosis groups and a "
            "reference group, with an effect size and a p-value.\n"
            "Use for any case/control question — schizophrenia, ASD, bipolar, "
            "affective disorder — in PsychENCODE, BrainSeq or Velmeshev.\n"
            "The test is run on DONOR MEANS where a dataset has many "
            "observations per donor, because a nucleus-level test on 3 donors "
            "inflates the p-value by orders of magnitude. The result therefore "
            "carries a 'statistical_note' with the effective sample size and a "
            "warning for any group below n=10; you MUST state it. Quote "
            "'statistical_note.text' rather than paraphrasing it.\n"
            "Raises a clear error for datasets with no Diagnosis column, and "
            "for HDBR, where every sample is a control."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"},
                "reference": {
                    "type": "string",
                    "description": (
                        "Reference group every other diagnosis is compared "
                        "against. Default 'Control'. Matched "
                        "case-insensitively."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "compare_cell_type_by_diagnosis",
        "description": (
            "WHICH CELL TYPE carries a case/control difference. Velmeshev "
            "pairs per-nucleus cell-type labels with ASD/control status, so "
            "this answers 'is the ASD difference in excitatory neurons or "
            "glia' — a question neither get_cell_type_expression (no "
            "diagnosis) nor compare_by_diagnosis (no cell types) can answer.\n"
            "Aggregated to donor x cell type before testing. Every cell type "
            "is tested without multiple-comparison correction, which the "
            "returned 'statistical_note' says explicitly — report it. Name the "
            "cell type from 'largest_difference'; do not scan the rows."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"},
                "reference": {
                    "type": "string",
                    "description": "Reference diagnosis. Default 'Control'.",
                },
                "resolution": {
                    "type": "string",
                    "description": (
                        "Cell-type column to group by. Default "
                        "'MajorCellType'; finer columns give too few donors "
                        "per cell to test."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "correlate_with_covariate",
        "description": (
            "Does a gene's expression track a sample covariate (RIN, PMI, pH, "
            "dissection score, numeric age)?\n"
            "This is the QC companion to any difference you report. "
            "get_variance_partition gives the technical SHARE but cannot say "
            "which covariate or in which direction; this ranks every numeric "
            "covariate by |rho|. Call it when you have just reported a "
            "regional, developmental or diagnostic difference and want to "
            "know whether tissue quality could explain it, or when the user "
            "asks about data quality or confounding.\n"
            "With no `covariate`, all are tested and ranked — usually what you "
            "want. If 'statistical_note' carries a covariate warning, state it "
            "alongside the difference it qualifies."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "Gene symbol, e.g. SHANK3"},
                "covariate": {
                    "type": "string",
                    "description": (
                        "Optional single covariate, e.g. 'RIN', 'PMI', 'pH'. "
                        "Omit to test and rank all of them."
                    ),
                },
            },
            "required": ["gene"],
        },
    },
    {
        "name": "correlate_genes",
        "description": (
            "Co-expression of two genes across one dataset's samples "
            "(Spearman and Pearson). Use for 'are X and Y co-expressed', 'do "
            "they move together', or any two-gene relationship question.\n"
            "Correlation is across samples, so it reflects shared variation "
            "with development, region and donor — the dominant axes in this "
            "data. It is NOT evidence of a regulatory or physical "
            "interaction, and the returned note says so; do not upgrade it."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {"type": "string", "description": "First gene symbol"},
                "other_gene": {"type": "string", "description": "Second gene symbol"},
            },
            "required": ["gene", "other_gene"],
        },
    },
    {
        "name": "get_cell_type_composition",
        "description": (
            "The CELL-TYPE MAKEUP of bulk tissue from MultiBrain "
            "deconvolution — what fraction of the tissue is neurons, "
            "astrocytes, microglia, oligodendrocytes, endothelia. Available "
            "for the five bulk datasets.\n"
            "This is a property of the TISSUE, not of any gene: no `gene` "
            "argument. Use for 'what is the cellular composition', 'how does "
            "the neuron fraction change across development', or to give "
            "context for a bulk expression result — a developmental "
            "expression change can reflect a shift in cell composition rather "
            "than per-cell regulation.\n"
            "Pass `group_by` (e.g. 'AgeInterval', 'Regions', 'Diagnosis') to "
            "see composition shift across a stratum. Returns a stacked "
            "proportion bar in 'table' with all percentages in its "
            "legend — keep your text to one or two sentences and do not "
            "enumerate the components.\n"
            "Distinct from get_cell_type_expression, which is per-nucleus "
            "expression in the single-nucleus datasets."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "group_by": {
                    "type": "string",
                    "description": (
                        "Optional metadata column to split composition by, "
                        "e.g. 'AgeInterval', 'Regions', 'Diagnosis'. Omit for "
                        "the dataset-wide mean."
                    ),
                },
            },
            "required": [],
        },
    },
    {
        "name": "find_genes_in_locus",
        "description": (
            "Which genes lie in a genomic interval (hg38), and which BITHub "
            "datasets quantify each one. Use when the user gives coordinates, "
            "a CNV, a GWAS locus or a cytoband-style range rather than gene "
            "names — e.g. 'what genes are in the 22q13 deletion region'.\n"
            "Overlap, not containment: a gene straddling a boundary is "
            "included. This is an ANNOTATION lookup and returns no expression "
            "values; call an expression tool separately if the user wants "
            "those. Requires the published data bundle; raises a clear error "
            "on a local-CSV instance, which has no coordinates."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "chromosome": {
                    "type": "string",
                    "description": "Chromosome, e.g. '22', 'X'. 'chr22' also accepted.",
                },
                "start": {"type": "integer", "description": "Interval start (hg38 bp)"},
                "end": {"type": "integer", "description": "Interval end (hg38 bp)"},
                "limit": {
                    "type": "integer",
                    "description": "Max genes to return. Default 100.",
                },
            },
            "required": ["chromosome", "start", "end"],
        },
    },
    {
        "name": "gene_info",
        "description": (
            "Identity, genomic position and DATASET COVERAGE for one gene — "
            "which BITHub datasets quantify it and which do not.\n"
            "Call this BEFORE an expression query when the user asks about a "
            "gene in a specific dataset and you are unsure it is present: "
            "coverage differs (HCA carries 20,630 genes, BrainSpan 30,687), "
            "and without this the absence surfaces as a failed query "
            "mid-answer. Also use for 'what is this gene', 'where is it', "
            "'is it in BITHub'.\n"
            "Returns no expression values."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "gene": {
                    "type": "string",
                    "description": "Gene symbol or Ensembl ID, e.g. SHANK3.",
                },
            },
            "required": ["gene"],
        },
    },
]

#: Tools that run against ONE dataset and therefore accept `dataset`.
#: compare_datasets is excluded (it takes a `datasets` LIST and spans the
#: selection), as is search_literature (external, not dataset-scoped) — adding
#: `dataset` to either would invite a call the dispatcher cannot honour.
_PER_DATASET_TOOLS = {
    "get_expression", "get_variance_partition", "get_dataset_metadata",
    "describe_metadata", "search_genes", "get_developmental_trajectory",
    "generate_figure", "get_cell_type_expression",
    "compare_by_diagnosis", "compare_cell_type_by_diagnosis",
    "correlate_with_covariate", "correlate_genes",
    "get_cell_type_composition", "find_genes_in_locus", "gene_info",
}

for _tool in TOOLS:
    if _tool["name"] in _PER_DATASET_TOOLS:
        _tool["input_schema"] = _with_dataset(_tool["input_schema"])

# A typo in _PER_DATASET_TOOLS would silently leave a schema unpatched, which
# is the exact class of bug this block fixes — so check the names match.
_declared = {t["name"] for t in TOOLS}
assert _PER_DATASET_TOOLS <= _declared, (
    f"_PER_DATASET_TOOLS names no such tool: {sorted(_PER_DATASET_TOOLS - _declared)}"
)
assert all("dataset" in t["input_schema"]["properties"]
           for t in TOOLS if t["name"] in _PER_DATASET_TOOLS)

SYSTEM_PROMPT = """You are BITHub Assistant, a research tool for exploring gene expression in the human brain across development.

Your data is BITHub: eight human brain transcriptomic datasets, in two families that answer different questions.

BULK TISSUE — one value per sample, a mixture of cell types, with developmental and regional axes:
  BrainSpan (524 samples, 8pcw-40yrs, cortex/subcortex/cerebellum, RPKM), BrainSeq (900, RPKM), HDBR (649, prenatal, RPKM), GTEx (2642, adult, TPM), PsychENCODE (1369, TPM).

SINGLE-NUCLEUS — one value per nucleus, labelled by cell type, with NO developmental period:
  HCA (46,958 nuclei, adult cortex, CPM), Velmeshev (81,215, ASD case/control cortex, CPM), Cameron (69,284, 13-15pcw, CPM).

Match the dataset family to the question: cell-type questions need single-nucleus data, developmental-trajectory questions need bulk. Units differ across all eight, so absolute values are comparable only within a dataset.

GROUNDING — these are hard rules, not preferences:
1. Never state an expression value, fold change, rank, or variance fraction that did not come back from a tool call in this conversation. If you have not called a tool, you do not know the number.
2. Never derive a superlative by inspection. Claims of the form "highest", "lowest", "steepest", "fastest-rising", "biggest change" must be read from a field a tool computed for you — get_developmental_trajectory returns steepest_transition and transitions_by_magnitude for exactly this reason. Reading a list of means and picking the pair that looks furthest apart is an error, even when the list is in front of you.
3. If a tool cannot answer the question, say so plainly. Do not substitute recalled knowledge for a measurement and do not present literature as if it were this dataset.
4. If a gene symbol is not found, call search_genes and offer the near matches.

TABLES — prefer them over prose for anything tabular:
5. Several tools return a "table" field that is already formatted for display. When one is present, the UI renders it automatically. Do NOT retype its numbers into a markdown table or a bulleted list — that duplicates the table and risks transcription errors. Refer to it ("the table below") and use your text for what the numbers mean.

5a. NEVER hand-write a markdown table — no pipe characters, no |---|---| separator rows. If values belong in a table, a tool returns one; if no tool returns the table you want, present the values as prose or a short bullet list instead. Hand-built tables are both a transcription risk and the main source of unreadable output.
6. Any answer that would otherwise be more than about three number-bearing bullets belongs in a table. Per-age-interval values, per-region comparisons, variance components and metadata summaries all have table-returning tools — call them.

SCOPE AND CROSS-DATASET CLAIMS:
7. Only the datasets listed as currently selected are queryable. If the user asks about one that is not loaded, say so plainly and name what you did use — never answer from a different dataset as though it were the one requested.
8. State units as log2(RPKM+1) for BrainSpan — it is RPKM, not TPM. BITHub's datasets do not share a unit: BrainSpan, BrainSeq and HDBR are RPKM, GTEx and PsychENCODE are TPM, Cameron, HCA and Velmeshev are CPM. Absolute expression values are therefore NOT comparable between datasets. Only the z-scored values from compare_datasets are, and that is also the scale the BITHub gene-view plots use.
9. "Corroborated", "replicates" and "consistent across datasets" are claims about two or more datasets. Make them only when compare_datasets returned comparison_possible: true with at least two rows. If it returned false, state that the comparison could not be made and why. One dataset agreeing with itself is not corroboration.
10. When datasets disagree, say so — report the direction and magnitude in each rather than averaging them into a single narrative. Disagreement between cohorts is a finding, not noise to smooth over.
11. When reporting on RIN, PMI, pH or dissection score, say how many samples actually have the value. describe_metadata returns this; several covariates are missing for a substantial minority of BrainSpan samples, and an analysis that quietly drops them is misleading.

TOOL USE:
12. Call get_developmental_trajectory for any question about change over development, timing, or trend shape — not get_expression, which returns period means only.
13. Call describe_metadata for questions about the dataset's contents rather than a gene's values — what variables exist, what range a covariate spans, which age intervals or regions are represented, how complete a field is.

13a. EVERY per-gene tool takes a `dataset` argument — get_expression, get_cell_type_expression, get_developmental_trajectory, get_variance_partition, describe_metadata, get_dataset_metadata, search_genes and generate_figure — and you MUST pass it whenever the user names a dataset — "what metadata is in BrainSeq" is describe_metadata(dataset="BrainSeq"), not a refusal and not BrainSpan's answer relabelled. This works for any loaded dataset regardless of which chips are selected; the selection governs gene queries, not what you may describe. The schemas genuinely differ — BrainSpan has 19 columns, BrainSeq 33, GTEx 49, Cameron 7 — so never answer for one dataset from another's metadata. To compare what several datasets record, call describe_metadata once per dataset.
13b. CELL TYPES. For any question about which cell type expresses a gene, or whether a signal is neuronal or glial, call get_cell_type_expression on a single-nucleus dataset (Cameron, HCA, Velmeshev). Never infer a cell type from a bulk dataset's regional pattern — cortex is not a cell type. The three datasets differ in scope and are not interchangeable: HCA is adult cortex, Velmeshev is ASD case/control cortex, Cameron is mid-gestation (13-15pcw) and its progenitor populations exist only prenatally. Name which one you used.

13c. The bulk datasets have NO cell-type labels; each sample is a mixture. get_cell_type_expression will refuse them, and that refusal is correct — do not retry it on another bulk set. What bulk data supports is get_variance_partition, whose cell-type-proportion components quantify how much variance tracks composition. "Variance explained by astrocyte proportion" and "expression in astrocytes" are different claims; do not report one as the other.

14. When the user asks to see, show, plot or visualise something, call generate_figure with the figure_type that matches the question: scatter for sample-level or continuous-covariate questions and anything specifying axes or encodings, heatmap for several genes at once, trajectory for developmental means, box for the distribution behind those means (spread, variability, whether groups overlap), variance for variance questions, expression otherwise. A table and a figure together is often the best answer. When you report a trajectory, consider pairing it with a box figure: the line shows where the mean moved, the boxes show whether the shift is large relative to the scatter within each group.
15. The scatter type is configurable — x, color_by and symbol_by accept any suitable metadata column. Before saying a plot is not possible, check whether scatter or heatmap with different arguments would produce it. If a requested encoding genuinely is not supported, say exactly which part is unavailable and offer the closest configuration you CAN produce, naming the arguments.
16. Call search_literature only when the user asks what is known about a gene, wants references, or asks an interpretive question. Skip it for pure expression or variance queries.

16a. If search_literature returns an "error" or "errors" field, say the literature lookup failed and why. Do NOT fill the gap from your own recollection and do NOT let the absence of citations read as "nothing is published" — those are different claims, and a reader cannot tell them apart unless you say which one it is.

STYLE:
17. Be concise and scientifically precise. Lead with the answer, then the evidence.

17a. STRUCTURE A REPORT. For anything beyond a one-line factual answer, open with a single bold sentence stating the finding, then use `##` section headings to organise the evidence. Choose headings that name what the section establishes — "Developmental pattern", "What drives the variance", "Regional differences", "Cross-dataset agreement", "Caveats" — not generic labels like "Results" or "Analysis". Three to five sections is usually right; one heading per idea.

17b. Do not use `###` as the top level, and do not label a closing section "Bottom line" — the opening sentence already carries the finding. Close with what the reader should look at next only when there is a genuinely useful follow-up, phrased as a specific question rather than a menu of options.

17c. Put the interpretation in prose paragraphs, not bullet fragments. Bullets are for genuinely parallel items — a list of caveats, a set of covariates. A paragraph that has been chopped into bullets reads as less rigorous, not more.
18. After any variance partition result, say which covariate dominates and give the technical total (RIN, PMI, pH, dissection score). Flag it explicitly when technical factors are a large share — that is the difference between a real biological signal and a tissue-quality artefact.

18a. A variance result renders as a PROPORTION BAR with every component and percentage already in its legend. Keep your accompanying text to ONE OR TWO SENTENCES: the dominant driver with its percentage, and the technical total. Do not enumerate the other components, do not restate the legend, and do not add a heading — the bar carries its own title. Two sentences and a bar is a complete answer; a paragraph plus the bar is worse than either alone, because the reader has to check whether the prose and the figure agree.
19. Write for a researcher who will check your numbers against the data."""


# ── Tool dispatcher ────────────────────────────────────────────────────────────

def dispatch_tool(name: str, args: dict, registry, datasets=None) -> str:
    """
    Route one tool call.

    `registry` holds every loaded dataset; `datasets` is the user's current
    selection. Per-gene tools run against a single dataset — the one named in
    the call, else the first selected — while compare_datasets spans the
    whole selection.
    """
    try:
        selection = datasets or registry.available
        if name == "compare_datasets":
            return json.dumps(registry.compare_expression(
                args["gene"], datasets=args.get("datasets") or selection,
            ))

        loader = registry.get(args.get("dataset") or selection[0])
        if name == "get_expression":
            # The loader already aggregates; returning 524 raw rows would just
            # burn context and invite the model to do arithmetic on them.
            return json.dumps(loader.get_expression(args["gene"]))

        elif name == "get_developmental_trajectory":
            return json.dumps(loader.get_developmental_trajectory(args["gene"]))

        elif name == "get_cell_type_expression":
            return json.dumps(loader.get_cell_type_expression(
                args["gene"],
                cell_type=args.get("cell_type"),
                resolution=args.get("resolution", "MajorCellType"),
            ))

        elif name == "get_variance_partition":
            return json.dumps(loader.get_variance_partition(
                args["gene"],
                cell_type_controlled=args.get("cell_type_controlled", False),
            ))

        elif name == "compare_by_diagnosis":
            return json.dumps(loader.compare_by_diagnosis(
                args["gene"], reference=args.get("reference", "Control"),
            ))

        elif name == "compare_cell_type_by_diagnosis":
            return json.dumps(loader.compare_cell_type_by_diagnosis(
                args["gene"], reference=args.get("reference", "Control"),
                resolution=args.get("resolution", "MajorCellType"),
            ))

        elif name == "correlate_with_covariate":
            return json.dumps(loader.correlate_with_covariate(
                args["gene"], covariate=args.get("covariate"),
            ))

        elif name == "correlate_genes":
            return json.dumps(loader.correlate_genes(
                args["gene"], args["other_gene"],
            ))

        elif name == "get_cell_type_composition":
            return json.dumps(loader.get_cell_type_composition(
                group_by=args.get("group_by"),
            ))

        elif name == "find_genes_in_locus":
            return json.dumps(loader.find_genes_in_locus(
                args["chromosome"], args["start"], args["end"],
                limit=int(args.get("limit", 100)),
            ))

        elif name == "gene_info":
            return json.dumps(loader.gene_info(args["gene"]))

        elif name == "get_dataset_metadata":
            return json.dumps(loader.get_dataset_metadata())

        elif name == "describe_metadata":
            return json.dumps(loader.describe_metadata(args.get("variable")))

        elif name == "search_genes":
            return json.dumps({"matches": loader.search_genes(args["query"])})

        elif name == "generate_figure":
            kind = args.get("figure_type", "expression")
            if kind == "heatmap":
                genes = args.get("genes") or ([args["gene"]] if args.get("gene") else [])
                result = loader.get_heatmap_figure(
                    genes,
                    group_by=args.get("group_by", "AgeInterval"),
                    scale=args.get("scale", "zscore"),
                )
            elif kind == "box":
                result = loader.get_box_figure(
                    args["gene"],
                    group_by=args.get("group_by", "AgeInterval"),
                    split_by=args.get("split_by"),
                )
            elif kind == "scatter":
                result = loader.get_scatter_figure(
                    args["gene"],
                    x=args.get("x", "AgeNumeric"),
                    color_by=args.get("color_by", "Regions"),
                    symbol_by=args.get("symbol_by", "Period"),
                    log_x=args.get("log_x", False),
                )
            elif kind == "trajectory":
                result = loader.get_trajectory_figure(args["gene"])
            elif kind == "variance":
                result = loader.get_variance_figure(
                    args["gene"],
                    cell_type_controlled=args.get("cell_type_controlled", False),
                )
            elif kind in ("composition", "composition_pie"):
                result = loader.get_composition_figure(
                    group_by=args.get("group_by"),
                    chart="pie" if kind == "composition_pie" else "stacked_bar",
                )
            else:
                result = loader.get_expression_figure(args["gene"])
            return json.dumps(result)

        elif name == "search_literature":
            return json.dumps(search_literature(
                args["gene_symbol"],
                context=args.get("context", "brain development expression"),
                limit=min(int(args.get("limit", 3)), 10),
            ))

        else:
            return json.dumps({"error": f"Unknown tool: {name}"})

    except ValueError as e:
        # Gene-not-found and similar: the model should recover, not crash.
        return json.dumps({"error": str(e)})
    except KeyError as e:
        return json.dumps({"error": f"Missing required argument: {e}"})
    except Exception as e:  # noqa: BLE001 - surface as a tool error, never a 500
        return json.dumps({"error": f"{type(e).__name__}: {e}"})


# ── Claude tool-calling loop ───────────────────────────────────────────────────

_api_key = os.environ.get("ANTHROPIC_API_KEY")
if not _api_key:
    raise RuntimeError(
        "ANTHROPIC_API_KEY is not set. Copy chatbot/.env.example to chatbot/.env "
        "and add your key, or export it in the shell before starting the server."
    )

client = anthropic.Anthropic(api_key=_api_key)
MODEL = os.environ.get("BITHUB_CHAT_MODEL", "claude-sonnet-4-6")
MAX_TOOL_ROUNDS = int(os.environ.get("BITHUB_MAX_TOOL_ROUNDS", "10"))


def run_agent(user_query: str, registry, history: list = None,
              datasets: list = None) -> dict:
    """
    Run the agent loop for a user query.

    Returns {"text", "last_gene", "figures", "figure", "literature", "tools_used"}.
    "figure" is the first figure, kept so existing single-figure clients keep working.
    """
    selection = datasets or registry.available
    messages = list(history) if history else []
    messages.append({"role": "user", "content": user_query})

    # Tell the model which datasets the user selected, so it does not have to
    # infer scope from the question text.
    system = SYSTEM_PROMPT + (
        f"\n\nCURRENTLY SELECTED DATASETS: {', '.join(selection)}."
        + (" The user selected more than one — prefer compare_datasets and "
           "report agreement or disagreement between them."
           if len(selection) > 1 else
           " Only one dataset is selected, so any claim you make is "
           "single-dataset. Do not describe it as corroborated across datasets.")
    )

    last_gene          = None
    figures            = []
    tables             = []
    literature_results = None
    tools_used         = []

    for _ in range(MAX_TOOL_ROUNDS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=system,
            tools=TOOLS,
            messages=messages,
        )

        if response.stop_reason != "tool_use":
            text = "".join(
                block.text for block in response.content if hasattr(block, "text")
            )
            return {
                "text":       text or "No response generated.",
                "last_gene":  last_gene,
                "figures":    figures,
                "figure":     figures[0] if figures else None,
                "tables":     tables,
                "literature": literature_results,
                "tools_used": tools_used,
            }

        messages.append({"role": "assistant", "content": response.content})

        tool_results = []
        for block in response.content:
            if block.type != "tool_use":
                continue

            result = dispatch_tool(block.name, block.input, registry, selection)
            parsed = json.loads(result)
            tools_used.append(block.name)

            if "error" not in parsed:
                # Track the gene in play so the UI can offer a handoff into
                # BITHub's gene view. Figure tools resolve genes too.
                if parsed.get("gene"):
                    last_gene = parsed["gene"]
                elif parsed.get("genes") and len(parsed["genes"]) == 1:
                    # A one-gene heatmap still identifies a gene for the handoff.
                    last_gene = parsed["genes"][0]

                if block.name == "generate_figure":
                    figures.append(parsed)

                # Tools carry a render-ready table; dedupe so a repeated call
                # in the same turn does not stack identical tables in the UI.
                table = parsed.get("table")
                if table and not any(t["title"] == table["title"] for t in tables):
                    tables.append(table)

                if block.name == "search_literature":
                    literature_results = parsed

            tool_results.append({
                "type":        "tool_result",
                "tool_use_id": block.id,
                "content":     result,
            })

        messages.append({"role": "user", "content": tool_results})

    return {
        "text": (
            "I reached the tool-call limit for this question without settling on an "
            "answer. Try asking about one gene at a time."
        ),
        "last_gene":  last_gene,
        "figures":    figures,
        "figure":     figures[0] if figures else None,
        "tables":     tables,
        "literature": literature_results,
        "tools_used": tools_used,
    }
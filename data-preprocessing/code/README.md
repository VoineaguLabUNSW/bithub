#  BITHub preprocessing utilities

This folder contains R utility functions used by the BITHub dataset preprocessing notebooks located in `docs/`.  

All preprocessing notebooks load these functions using:

```r
source(here::here("code/functions.R"))
```
## Metadata pre-processing 

These functions standardise metadata naming, derive harmonised features, summarise metadata, and remove redundant sequencing metrics prior to inclusion in BITHub.

### Preprocessing pipeline overview
Across datasets (BrainSeq, BrainSpan, GTEx, HDBR, PsychENCODE), the preprocessing notebooks follow the same high-level pipeline:

```{r}
Raw metadata + expression
        ↓
Rename metadata columns to BITHub standards
        ↓
Derive harmonised features (age bins, regions, periods)
        ↓
Profile metadata (categorical + numeric)
        ↓
Filter redundant / uninformative metadata
        ↓
Export formatted metadata and annotation files
```

In code, this typically looks like:

```{r}
md <- rename_from_annot(md, annot)

md <- md %>%
  mutate(
    Period = ifelse(`Age (Numeric)` >= 0, "Postnatal", "Prenatal"),
    Regions = add_feature(`Structure Acronym`, regions),
    Age_rounded = sapply(`Age (Numeric)`, num_to_round),
    `Age Interval` = add_feature(Age_rounded, age_intervals)
  )

cat_tbl <- cat_summary(md)

seq_cols <- get_seq_metrics_cols(annot)
res <- select_seq_metrics(md, seq_cols)
```


### Functions: 

```{r}
rename_from_annot(
  df,
  annot,
  from = "OriginalMetadataColumnName",
  to   = "BITColumnName",
  strict = TRUE
)
```

Renames metadata columns to BITHub-standard names using a dataset-specific annotation file (from data/annotations/).

**Purpose**  
- Ensures consistent column names across datasets  
- Enforces alignment with `data/annotations/*.csv`

**Arguments**  
- `df`: metadata `data.frame`  
- `annot`: annotation mapping table  
- `from`: column in `annot` containing original column names  
- `to`: column in `annot` containing BITHub column names  
- `strict`: if `TRUE`, stops when unmapped columns are detected  

**Returns**  
- Renamed `data.frame`  

**Used in**  
All datasets

```{r}
add_feature(feature_column, features)
```
Maps metadata values to harmonised labels using a predefined lookup list.

**Purpose**
Collapse dataset-specific labels into shared BITHub categories

**Arguments**
-`feature_column`: vector of values to map
-`features`: named list (label → values)

**Returns**
- Character vector of mapped labels

```{r example-usage}
Regions <- add_feature(`Structure Acronym`, regions)
AgeInterval <- add_feature(Age_rounded, age_intervals)
```


```{r}
num_to_round(age)
```

Converts numeric ages into rounded, human-readable labels.

**Rules** 
- `age >= 2 → "X yrs"`
- `0 <= age < 2 → "X mos"`
- `age < 0 → "X pcw"`

**Returns**
Character string

**Used for**
Age display and binning prior to Age Interval mapping


```{r}
cat_summary(df, max_show = 50, na_label = "(NA)")
```
Summarises categorical metadata columns.

**Purpose**
- Identify high-cardinality or non-informative categorical variables

**Output**
-One row er categorical column with:
    - number of unique values
    - listed values (or > max_show)

**Used for**
Metadata filtering decisions across all datasets


```{r}
profile_df(
  df,
  cat_max_levels = 50,
  top_n_levels = Inf,
  bins = 30,
  na_label = "(NA)"
)
```
Generates exploratory summaries and plots for metadata.

**Returns**
- categorical_tables
- categorical_plots
- numeric_summary
- numeric_plots


**Used for**
Producing tables and figures shown directly in the preprocessing `Rmds`


```{r}
get_seq_metrics_cols(
  annot,
  type_col = "Type",
  name_col = "BITColumnName"
)
```
Extracts sequencing-metric metadata columns from a dataset annotation file.


**Purpose**

Identify which metadata columns should be evaluated for redundancy

**Returns**
Character vector of sequencing-metric column names


```{r}
select_seq_metrics(
  md,
  seq_cols,
  corr_thresh = 0.9,
  missing_thresh = 0.5,
  min_unique = 2,
  prefer = "less_missing"
)
```
Filters sequencing metrics to retain a non-redundant and interpretable subset.
Filtering steps
Drop columns that are:
- all missing
- low variability
- mostly missing
- Identify highly correlated metrics (Spearman correlation)
- Retain one representative metric per correlated pair

**Returns**
```{r}
list(
  keep,
  drop,
  summary,
  correlated_pairs
)
```

**Used for**
BrainSeq, BrainSpan, GTEx, HDBR



- Single-nucleus utilities used in this R Markdown

These functions support Seurat-based preprocessing and conversion to CPM-like matrices.


```{r}
get.max.depth()
```

**Purpose**
	-	Computes an upper library-size cutoff for snRNA-seq QC filtering
	-	Uses a percentile threshold (max.depth.percentile) defined in functions.R

**Arguments**
	-	x: Seurat object

**Returns**
  -	Numeric maximum depth value (library size cutoff)

**Used in**
	-	HCA, Velmeshev et al, Cameron et al
	
```{r}	
preprocess.fun()
```
**Purpose**
	- Applies standard Seurat QC + normalisation workflow:
	-	mitochondrial fraction calculation
	-	filtering on depth and mitochondrial reads
	-	optional downsampling
	-	normalisation + variable feature selection
	-	optional SCTransform

**Arguments**
	-	x: Seurat object
	-	run.downsample: whether to downsample (default driven by global downsample)
	-	SCTransform: whether to run SCTransform (default driven by global use.SCTransform)
	-	max.depth: max library-size cutoff (typically from get.max.depth())

**Returns**
	-	Updated Seurat object after QC + normalisation

Used in
	•	HCA, Velmeshev et al, Cameron et al


```{r}
make.cpm()
```

**Purpose**
	•	Performs library-size correction to convert counts to CPM-like values
	•	Scales each column to sum to 1e6

**Arguments**
	•	x: gene-by-cell count matrix

**Returns**
	•	CPM-like matrix

**Used in**
	•	HCA, Velmeshev et al, Cameron et al


#### Notes
Dataset-specific lookup tables are defined in:

-`def_stages.R`
-`def_regions.R`
-`def_death.R`

Processed metadata outputs are written to:
`output/metadata/`

Final “included metadata” annotation files are written back to:
`data/annotations/*-annot-final.csv`


## Cell type deconvolution 

In progress 

## Variance parititioning 

In progress

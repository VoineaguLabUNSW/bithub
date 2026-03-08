# Data pre-processing code for BITHub 
This repository contains the data preprocessing code used to curate, harmonise, and analyse transcriptomic datasets included in BITHub. It covers bulk and single-nucleus RNA-seq datasets from multiple human brain resources and produces standardised metadata, expression matrices, and downstream analysis outputs used by the BITHub platform. 

# How to run the preprocessing
	1.	Clone the repository.
	2.	Open `config/paths-example.yaml` and input the raw data paths.
	3.	Open `data-preprocessing.Rproj`.
	4.	Run notebooks in `notebooks/` as needed (starting with `metadata-preprocess.Rmd`).

Each notebook is self-contained and documents dataset-specific decisions inline.



# Data 
Both bulk and single-nucleus RNA-seq human brain transcriptomic datasets were retrieved from their respective public portals, as summarised below.

| Dataset | Modality | Description | nSamples / nCells | Source |
|-------|---------|-------------|------------------|--------|
| **BrainSeq** | Bulk RNA-seq | Post-mortem hippocampus and DLPFC; prenatal and adult samples; includes schizophrenia cases | 900 samples | [BrainSeq Phase II](https://eqtl.brainseq.org/phase2/) |
| **BrainSpan** | Bulk RNA-seq | Developmental atlas across multiple brain regions; prenatal to adult neurotypical samples | 524 samples | [BrainSpan Atlas](https://www.brainspan.org/static/download.html) |
| **GTEx** | Bulk RNA-seq | Post-mortem brain tissue from non-diseased individuals across 13 regions | 2,642 samples | [GTEx v8](https://gtexportal.org/home/datasets) |
| **HDBR** | Bulk RNA-seq | Prenatal human brain developmental transcriptomes | 159 samples | Data downloaded from `recount3` |
| **PsychENCODE** | Bulk RNA-seq | DLPFC samples spanning prenatal and postnatal development; control and psychiatric disorders | 1,866 samples | [PsychENCODE](http://resource.psychencode.org) |
| **Human Cell Atlas** | snRNA-seq | Single-nucleus transcriptomes of the human brain | 32,749 cells | [Human Cell Atlas]()https://chatgpt.com/c/69856e3d-b750-839b-a30d-dd331ae817ab |
| **Velmeshev et al.** | snRNA-seq | Single-nucleus data from PFC, ACC, and insular cortex; control and ASD | 81,216 cells | [UCSC Cell Browser](https://cells.ucsc.edu/?ds=autism) |
| **Cameron et al.** | Bulk RNA-seq | Post-mortem human brain transcriptomes | — | [Cameron et al](https://www.biologicalpsychiatryjournal.com/article/S0006-3223(22)01404-4/fulltext) |




## Repository structure 

```
├── code/                 # Reusable functions and lookup definitions
├── config/               # User-specific configuration (paths)
├── data/                 # Annotation files and reference data
├── notebooks/            # Dataset preprocessing and analysis notebooks
├── output/               # Generated metadata, results, and figures
└── README.md             # This file
```


# code/

Reusable R functions and definitions shared across all datasets.
'functions.R':
Core utility functions for:
	-	metadata harmonisation
	-	feature derivation (age bins, regions, stages)
	-	metadata profiling
	-	sequencing-metric redundancy filtering


- `def_regions.R`, `def_stages.R`, `def_death.R`
	Lookup tables used to derive harmonised BITHub features.
	
	
`fun-cibersort.R`:
Helper functions for bulk RNA-seq cell-type deconvolution.

Each function is documented in code/README.md.


## config/

Configuration files defining local paths to raw data and output directories.
'paths-example.yaml':

Template file showing the expected structure.

Users should copy this file (e.g. to paths.yaml) and edit paths to match their local environment.

No hard-coded file paths are used in the notebooks; all file locations are read from the config.


## notebooks/

All dataset preprocessing and analysis steps are implemented as R Markdown notebooks.

Key notebooks include:
	--metadata-preprocess.Rmd
		dataset-specific metadata loading
	•	harmonisation and filtering
	•	exploratory profiling
	•	generation of final metadata tables

-- bulk-deconvolution.Rmd
	•	bulk RNA-seq cell-type deconvolution using reference signatures
	* goodness-of-fit to evaluate deconvolution

-- drivers-of-variation.Rmd
	•	variance partitioning and analysis of drivers of expression variation

-- main-figures.Rmd
	•	generation of figures used in the BITHub manuscript


Notes
	•	This repository focuses on data preprocessing and analysis, not on hosting raw data.
	•	All filtering, harmonisation, and metadata-selection decisions are documented in the notebooks.
	•	Outputs committed to `output/` reflect the versions used for BITHub.


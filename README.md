# Brain Integrative Transcriptome Hub (BITHub)

BITHub is an web resource that allows exploration of gene expression across eight curated large-scale transcriptomic datasets of the human post-mortem brain. It integrates, harmonises, and standardises data from multiple studies to enable consistent cross-dataset exploration of gene-level expression patterns across brain regions, developmental stages, and clinical contexts.


BITHub is designed to support both interactive biological exploration and reproducible computational analysis.

## Project structure

```
bithub/
├── data-preprocessing/   # Dataset-specific cleaning and harmonisation
├── pipeline/             # Data packing, scaling, and transformation
├── frontend/             # Interactive web interface
└── README.md

```

`data-preprocessing/`: Dataset-specific scripts to clean, harmonise, and annotate raw expression and metadata files.
`pipeline/`:Unified processing pipeline that transforms preprocessed data into analysis-ready formats used by the frontend (e.g. z-score normalisation, gene filtering, dataset packing).
`frontend/` The interactive web application that powers BITHub, allowing users to search and explore expression patterns across datasets.

## Datasets available on BITHub
BITHub currently integrates eight curated, large-scale transcriptomic datasets derived from human post-mortem brain tissue.
These datasets span multiple brain regions, developmental stages, and disease contexts, and were selected based on cohort size, data quality, and metadata availability.


## Data processing overview  

![alt text](https://github.com/VoineaguLabUNSW/bithub/blob/main/methods_flowchart_v1.png)


The expression files were pre-processed using the code in the `data-preprocessing` folder, whereas the data packing pipeline, including the z-score transformations are in the `pipelines` folder.

### 1. Dataset-specific preprocessing (`data-preprocessing/`)

This stage includes:
- Cleaning and formatting raw expression matrices
- Curating and filtering metadata
- Defining anatomical regions and developmental stages
- Removing low-quality or non-informative samples and features

### 2. Unified pipeline processing (`pipeline/`)
This stage converts preprocessed datasets into a common format used by the frontend:
- Gene-level filtering and alignment across datasets
- Z-score transformation within datasets
- Packaging of expression and metadata into lightweight, queryable objects

This separation ensures that raw data handling decisions are clearly distinguished from downstream transformations.

### How to reproduce the analysis 

**Step 1: Clone the repository**

```
https://github.com/VoineaguLabUNSW/bithub.git
```

**Step 2: Open data pre-processiong**

```
cd bithub/data-preprocessing
```

**Step 3: Change the config file**
All dataset-specific input and output paths for preprocessing are defined in `data-preprocessing/config/paths-example.yaml`.  
Before running any preprocessing scripts update the entries so they match the locations of your local/raw data files and desired output directories.

**Step 4: Run the preprocessing for the invidual datasets**

### Step 4: Run preprocessing notebooks (order matters)

All preprocessing and exploratory analyses are implemented as **R Markdown notebooks** located in  
`data-preprocessing/notebooks/`.

These notebooks must be run **in the following order**, as each step depends on outputs generated in the previous one:

1. **`metadata-preprocess.Rmd`**  
   Cleans, filters, and harmonises metadata across datasets, including variable selection and annotation standardisation.

2. **`bulk-deconvolution.Rmd`**  
   Performs bulk tissue deconvolution using the harmonised metadata and expression matrices to estimate cell-type composition.

3. **`drivers-of-variation.Rmd`**  
   Identifies major technical and biological sources of variation in the data and evaluates their impact on gene expression patterns.

In addition, two R Markdown files are provided for figure generation:
- A notebook for **main figures**
- A notebook for **supplementary figures**

Each of these has a corresponding pre-rendered `.html` file for easy inspection without rerunning the analysis.

> All notebooks read input paths from the configuration file defined in `config/paths-example.yaml`.


**Step 5: Run the data packing pipleine**
Once the expression and metadata matrices are generated, run the data packing pipeline [In progress - for Kieran to complete]

## User interface

BITHub supports flexible gene-centric exploration, including:
### Search by gene symbol

Selection of datasets for comparison
Stratification by brain region
Stratification by developmental stage
Filtering based on available clinical or technical metadata
These options allow users to explore both dataset-specific patterns and cross-study consistency.



## Interactive data exploration

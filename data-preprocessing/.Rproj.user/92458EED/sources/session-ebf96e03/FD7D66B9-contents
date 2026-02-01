# BITHub pre-processing utility functions
# Author: Urwah Nawaz & Gavin Sutton

# Loading libraries and requirements
libs = c("dplyr", "ggplot2", "reshape2", "tools", "magrittr", "tibble", "readxl",
         "data.table", "scales", "tidyr",
         "reshape2", "stringr", "tidyverse",
         "readxl", "corrplot", "purrr", "DeconRNASeq",
         "DTWBI", "ModelMetrics", "dtangle")
libsLoaded = lapply(libs,function(l){suppressWarnings(suppressMessages(library(l, character.only = TRUE)))})


## Metadata pre-processing functions

### Change metadata name from Original to BITHub defined names as in annotation files
rename_from_annot <- function(df, annot,
                              from = "OriginalMetadataColumnName",
                              to   = "BITColumnName",
                              strict = TRUE) {
  m <- match(colnames(df), annot[[from]])
  if (strict && anyNA(m)) {
    missing <- colnames(df)[is.na(m)]
    stop("Unmapped columns in annot: ", paste(missing, collapse = ", "))
  }
  new_names <- colnames(df)
  new_names[!is.na(m)] <- annot[[to]][m[!is.na(m)]]
  colnames(df) <- new_names
  df
}

## Adding a pre-defined feature to a metadata
add_feature = function(feature_column, features){
  as.vector(sapply(feature_column, function(x){
    names(features)[sapply(features, function(f) x %in% f)]}))
}

## Convert a numeric age to round
num_to_round = function(age){
  if (is.na(age)) {
    NaN
  } else if (age >= 2) {
    paste0(round(age), " yrs")
  } else if (age < 0) {
    paste0(round(age * 52 + 40), " pcw")
  } else if (age >= 0 & age < 2) {
    paste0(round(age * 12), " mos")
  }
}

### Function to show plots for the data

profile_df <- function(df,
                       cat_max_levels = 50,
                       top_n_levels = Inf,     # show top N in plots
                       bins = 30,
                       na_label = "(NA)") {


  is_cat <- function(x) is.character(x) || is.factor(x) || is.logical(x)
  is_num <- function(x) is.numeric(x) || inherits(x, "integer")


  cat_cols <- names(df)[map_lgl(df, is_cat)]

  cat_tables <- map(cat_cols, function(col) {
    df %>%
      mutate(.x = .data[[col]],
             .x = ifelse(is.na(.x), na_label, as.character(.x))) %>%
      count(.x, sort = TRUE) %>%
      mutate(prop = n / sum(n),
             column = col) %>%
      relocate(column)
  }) %>% set_names(cat_cols)

  ## Categorial boxplots
  cat_tables <- cat_tables[map_int(cat_tables, nrow) <= cat_max_levels]

  cat_plots <- imap(cat_tables, function(tab, col) {
    tab_plot <- tab %>% slice_head(n = top_n_levels)

    ggplot(tab_plot, aes(x = fct_reorder(.x, n), y = n)) +
      geom_col() +
      coord_flip() +
      labs(title = paste0(col),
           x = NULL, y = "Count") +
      theme_bw()
  })

 ## Numeric histograms
  num_cols <- names(df)[map_lgl(df, is_num)]

  num_summary <- map_dfr(num_cols, function(col) {
    x <- df[[col]]
    tibble(
      column = col,
      n = sum(!is.na(x)),
      n_na = sum(is.na(x)),
      min = suppressWarnings(min(x, na.rm = TRUE)),
      q1  = suppressWarnings(quantile(x, 0.25, na.rm = TRUE, names = FALSE)),
      median = suppressWarnings(median(x, na.rm = TRUE)),
      mean   = suppressWarnings(mean(x, na.rm = TRUE)),
      q3  = suppressWarnings(quantile(x, 0.75, na.rm = TRUE, names = FALSE)),
      max = suppressWarnings(max(x, na.rm = TRUE)),
      sd  = suppressWarnings(sd(x, na.rm = TRUE))
    )
  })

  num_plots <- set_names(num_cols) %>%
    map(function(col) {
      ggplot(df, aes(x = .data[[col]])) +
        geom_histogram(bins = bins) +
        labs(title = paste0(col), x = col, y = "Count") +
        theme_minimal()
    })

  list(
    categorical_tables = cat_tables,
    categorical_plots  = cat_plots,
    numeric_summary    = num_summary,
    numeric_plots      = num_plots
  )
}


### Function to harmonize common fields in metadata
harmonise_common_fields <- function(md,
                                    structure_map = NULL,
                                    regions_map = NULL,
                                    regions_fn = NULL) {
  md <- as.data.frame(md)

  # Structure Acronym cleanup
  if ("Structure Acronym" %in% names(md) && !is.null(structure_map)) {
    md[["Structure Acronym"]] <- recode_col(md[["Structure Acronym"]], structure_map, keep_unmapped = TRUE)
  }

  # Regions derivation
  if (!("Regions" %in% names(md)) && "Structure Acronym" %in% names(md)) {
    if (!is.null(regions_fn)) {
      md[["Regions"]] <- regions_fn(md[["Structure Acronym"]])
    } else if (!is.null(regions_map)) {
      # regions_map is list(region -> vector of structure acronyms)
      md[["Regions"]] <- sapply(md[["Structure Acronym"]], function(s) {
        hit <- names(regions_map)[sapply(regions_map, function(v) s %in% v)]
        if (length(hit) == 0) NA_character_ else hit[[1]]
      })
    }
  }

  # Adding developmental period (if Age numeric exists)
  if (!("Period" %in% names(md)) && "Age (Numeric)" %in% names(md)) {
    md[["Period"]] <- ifelse(md[["Age (Numeric)"]] >= 0, "Postnatal", "Prenatal")
  }

  md
}


get_seq_metrics_cols <- function(annot, type_col = "Type", name_col = "BITColumnName") {
  annot %>%
    dplyr::filter(.data[[type_col]] == "Sequencing metrics") %>%
    dplyr::pull(.data[[name_col]]) %>%
    unique()
}




select_seq_metrics <- function(md,
                               seq_cols,
                               corr_thresh = 0.9,
                               missing_thresh = 0.5,
                               min_unique = 2,
                               prefer = c("less_missing", "more_variable")) {

  prefer <- match.arg(prefer)
  md_seq <- md[, seq_cols, drop = FALSE]

  # ---------- describe columns ----------
  col_desc <- tibble(
    Metric = colnames(md_seq),
    n_total = nrow(md_seq),
    n_missing = sapply(md_seq, function(x) sum(is.na(x) | x == "")),
    frac_missing = n_missing / n_total,
    n_unique_nonmissing = sapply(md_seq, function(x) length(unique(x[!(is.na(x) | x == "")]))),
    class = sapply(md_seq, function(x) class(x)[1])
  )

  # Drop rules: all missing / single-value / too missing
  drop_reason <- rep(NA_character_, nrow(col_desc))
  drop_reason[col_desc$n_unique_nonmissing < 1] <- "All missing"
  drop_reason[is.na(drop_reason) & col_desc$n_unique_nonmissing < min_unique] <- paste0("Low variability (<", min_unique, " unique)")
  drop_reason[is.na(drop_reason) & col_desc$frac_missing > missing_thresh] <- paste0("Too missing (>", missing_thresh, ")")

  col_desc <- col_desc %>%
    mutate(drop_reason = drop_reason,
           keep_stage1 = is.na(drop_reason))

  kept_stage1 <- col_desc %>% dplyr::filter(keep_stage1) %>% pull(Metric)

  # ---------- correlations (numeric only) ----------
  # attempt numeric coercion for correlation
  numeric_md <- md_seq[, kept_stage1, drop = FALSE] %>%
    mutate(across(everything(), ~ suppressWarnings(as.numeric(as.character(.x)))))

  is_numeric <- sapply(numeric_md, function(x) !all(is.na(x)) && is.numeric(x))
  numeric_cols <- names(is_numeric)[is_numeric]

  cor_pairs <- tibble()
  drop_cor <- character()

  if (length(numeric_cols) >= 2) {
    cor_mat <- suppressWarnings(cor(numeric_md[, numeric_cols, drop = FALSE],
                                    use = "pairwise.complete.obs",
                                    method = "spearman"))

    # upper triangle -> pairs
    ut <- which(upper.tri(cor_mat), arr.ind = TRUE)
    pairs <- tibble(
      metric_a = rownames(cor_mat)[ut[, 1]],
      metric_b = colnames(cor_mat)[ut[, 2]],
      corr = cor_mat[ut]
    ) %>%
      dplyr::filter(!is.na(corr)) %>%
      mutate(abs_corr = abs(corr)) %>%
      arrange(desc(abs_corr))

    cor_pairs <- pairs %>% dplyr::filter(abs_corr >= corr_thresh)

    # decide keep/drop per correlated pair
    if (nrow(cor_pairs) > 0) {
      # helper scores
      miss <- setNames(col_desc$frac_missing[match(numeric_cols, col_desc$Metric)], numeric_cols)

      # variability proxy: sd (on numeric data)
      sds <- sapply(numeric_md[, numeric_cols, drop = FALSE], function(x) suppressWarnings(sd(x, na.rm = TRUE)))
      sds[is.na(sds)] <- 0

      choose_drop <- function(a, b) {
        if (prefer == "less_missing") {
          if (miss[a] < miss[b]) return(b)
          if (miss[b] < miss[a]) return(a)
          # tie-breaker: keep more variable
          if (sds[a] >= sds[b]) return(b) else return(a)
        } else {
          if (sds[a] >= sds[b]) return(b) else return(a)
        }
      }

      cor_pairs <- cor_pairs %>%
        rowwise() %>%
        mutate(drop_suggested = choose_drop(metric_a, metric_b),
               keep_suggested = ifelse(drop_suggested == metric_a, metric_b, metric_a)) %>%
        ungroup()

      drop_cor <- unique(cor_pairs$drop_suggested)
    }
  }

  final_keep <- setdiff(kept_stage1, drop_cor)

  # ---------- outputs ----------
  summary_tbl <- col_desc %>%
    mutate(
      keep_final = keep_stage1 & !(Metric %in% drop_cor),
      drop_reason_final = case_when(
        !keep_stage1 ~ drop_reason,
        Metric %in% drop_cor ~ paste0("Highly correlated (|rho|>=", corr_thresh, ")"),
        TRUE ~ NA_character_
      )
    ) %>%
    dplyr::select(Metric, class, n_total, n_missing, frac_missing, n_unique_nonmissing,
                  keep_final, drop_reason_final) %>%
    arrange(desc(keep_final), desc(n_unique_nonmissing), frac_missing)

  list(
    keep = final_keep,
    drop = setdiff(seq_cols, final_keep),
    summary = summary_tbl,
    correlated_pairs = cor_pairs
  )
}


is_cat <- function(x) is.character(x) || is.factor(x) || is.logical(x)


cat_summary <- function(df, max_show = 50, na_label = "(NA)") {
  cat_cols <- names(df)[map_lgl(df, is_cat)]

  imap_dfr(df[cat_cols], function(x, col) {
    # treat values consistently
    x_chr <- as.character(x)
    x_chr[is.na(x_chr)] <- na_label

    vals <- sort(unique(x_chr))
    n_u  <- length(vals)

    tibble(
      column = col,
      n_unique = n_u,
      values = if (n_u > max_show) {
        paste0("> ", max_show)
      } else {
        paste(vals, collapse = ", ")
      }
    )
  })
}


## Normalization and single nucleus

## Key parameters
# for seurat preprocessing
min.cells <- 0 # during the initial load, a gene is excluded if in < 0 cells
min.features <- 200 # during the initial load, a barcode is excluded < 200 features are expressed
min.depth <- 1000 # a barcode is excluded if nCount_RNA < this value
max.depth.percentile <- 0.995 # a barcode is excluded if nCount_RNA > this percentile within the dataset
max.mito <- 5
min.celltype.n <- 0 # minimum number of members in a celltype for it to be kept. applied to anything used for creating mixtures (at this stage, Vel and HCA, but the former passes this criterion for all celltypes anyway...)

# preprocessing options
downsample <- FALSE
downsample.n <- NA; if (downsample) downsample.n <- NA
use.SCTransform <- FALSE


## General function for preprocessing sn data (normalise, filters, and scales)
get.max.depth <- function(x) {
  max.depth <- quantile(x@meta.data$nCount_RNA, probs = max.depth.percentile)
}

preprocess.fun <- function(x, run.downsample = downsample, SCTransform = use.SCTransform, max.depth = max.depth) {
  # quantify mitochondrial reads
  x[["percent.mito"]] <- PercentageFeatureSet(object = x, pattern = "^MT-")

  # filter to remove outlier nuclei:

  x <- subset(x = x, subset = (nCount_RNA > min.depth) & (nCount_RNA < max.depth) & (percent.mito < max.mito))

  # downsample
  if (run.downsample) { x <- downsample.fun(x) }

  # normalise expression levels
  x <- NormalizeData(object = x, normalization.method = "LogNormalize", scale.factor = 10000) # standard parameters for Seurat

  # find variable genes (i.e. features)
  x <- FindVariableFeatures(object = x, selection.method = "vst", nfeatures = 2000)


  # further normalisation
  if (use.SCTransform) {
    x <- SCTransform(object = x, vars.to.regress = c("nCount_RNA", "percent.mito"))
  }

  # output
  return(x)
}

## CPM
cpm = function(matrix){
  apply(matrix, 2, function(x) {
    lib.size <- 10^6 / sum(x)
    x <- x * lib.size
    return(x)
  })}

## RPKM
## geneList being rowname of features
getLength = function(geneList){
  ensembl <- useEnsembl(biomart = "genes", dataset = "hsapiens_gene_ensembl", mirror = "useast")
  annotations <- biomaRt::getBM(mart = ensembl, attributes=c("ensembl_gene_id", "external_gene_name", "start_position", "end_position"))
  annotations <- dplyr::transmute(annotations, ensembl_gene_id, external_gene_name, gene_length = end_position - start_position)
  x = annotations %>% dplyr::filter(annotations$ensembl_gene_id %in% geneList)
  x <- x[order(match(x$ensembl_gene_id, geneList)),]; rownames(x) <-NULL
  return(x)
}

rpkm = function(exp, gene_length){
  x = data.frame(sapply(exp, function(column) 10^9 * column / gene_length / sum(column)))
  rownames(x) = rownames(exp)
  return(x)
}

calculate_rpkm = function(exp){

  ## Retrieve gene lengths from bioMart
  ensembl <- useEnsembl(biomart = "genes", dataset = "hsapiens_gene_ensembl", mirror = "useast")
  annotations <- biomaRt::getBM(mart = ensembl, attributes=c("ensembl_gene_id", "external_gene_name", "start_position", "end_position"))
  annotations <- dplyr::transmute(annotations, ensembl_gene_id, external_gene_name, gene_length = end_position - start_position)

  ## Ensure gene lengths match exp matrix
  final.genes <- annotations %>% dplyr::filter(annotations$ensembl_gene_id %in% rownames(exp))
  final.genes <- final.genes[order(match(final.genes$ensembl_gene_id, rownames(exp))),]; rownames(final.genes) <-NULL

  exp.rpkm = signatures[rownames(exp) %in% final.genes$ensembl_gene_id,]
  expression.rpkm <- data.frame(sapply(exp.rpkm, function(column) 10^9 * column / final.genes$gene_length / sum(column)))
  rownames(expression.rpkm) = rownames(exp.rpkm)
  return(expression.rpkm)
}

## Function for library size correction
make.cpm <- function(x) {
  for (j in 1:ncol(x)) {
    x[,j] <- x[,j] / sum(x[,j]) * 10^6
  }
  return(x)
}

## Function to reclassify subtypes to major cell-types
rename <- function(old, new, m = meta) {
  m$MajorCelltype[grep(old, m$MajorCelltype)] <- new
  return(m)
}


## Deconvolution analysis functions - Adapted from Sutton et al (2022)

## Deconvolution functions

run.DRS <- function(mixture, signature) {
  res <- as.data.frame(DeconRNASeq(mixture, signature, use.scale = TRUE)$out.all)
  rownames(res) <- colnames(mixture)
  return(res)
}



write.gof<- function(measuredExp, estimatedComp, signatureUsed, returnPred = FALSE) {
  # set to common row order
  commonGenes <- rownames(measuredExp)[which(rownames(measuredExp) %in% rownames(signatureUsed))]
  measuredExp <- measuredExp[commonGenes,]; signatureUsed <- signatureUsed[commonGenes,]

  # quantile normalise
  qn <- data.frame(signatureUsed, measuredExp)
  qn <- as.data.frame(normalize.quantiles(as.matrix(qn), copy = FALSE))
  signatureUsed <- qn[,1:ncol(signatureUsed)]
  measuredExp <- qn[,-c(1:ncol(signatureUsed))]

  # predict expression (predExp) from the estimatedComp * signatureUsed
  predExp <- as.data.frame(matrix(nrow = length(commonGenes), ncol = ncol(measuredExp)))
  rownames(predExp) <- commonGenes

  for(j in 1:ncol(predExp)) {
    # storage
    a <- list()

    # the contribution of each cell-type to predicted expression
    for(k in colnames(signatureUsed)) { a[[k]] <- estimatedComp[j,k] * signatureUsed[,k] }

    # sum expression from all cell-types to a single predicted value
    predExp[,j] <- rowSums(do.call("cbind", a))
  }

  ## Calculate statistics
  stats <- as.data.frame(matrix(ncol = 5, nrow = ncol(measuredExp)))
  colnames(stats) <- c("rho", "r", "mae", "rmse", "nmae")
  rownames(stats) <- colnames(measuredExp)
  for(j in 1:ncol(measuredExp)) {
    a <- measuredExp[,j]
    b <- predExp[,j]
    stats$r[j] <- cor(log2(a+0.5), log2(b+0.5), method = "p")
    stats$rho[j] <- cor(a, b, method = "s")
    stats$mae[j] <- mae(a, b)
    stats$rmse[j] <- rmse(a, b)
    stats$nmae[j] <- compute.nmae(a, b)
  }
  # return
  if(returnPred) {
    res <- list()
    res$predExp <- predExp
    res$stats <- stats
  } else {
    res <- stats
  }

  return(res)
}




create.seurat.signature <- function(w) {
  # print
  print(w@project.name)

  # get counts
  counts <- as.data.frame(w@assays$RNA@counts)

  # convert to EnsID and remove non-coding genes
  counts <- addENSID(counts)

  # get CPM of every cell
  cpm <- apply(counts, 2, function(x) {
    lib.size <- 10^6 / sum(x)
    x <- x * lib.size
    return(x)
  })

  cpm <- as.data.frame(cpm)

  # get RPKM of every cell
  rpkm <- length.correct(cpm)

  # signatures are the average normalised expression of every member
  output <- list(rpkm = list(), cpm = list())
  for (j in rownames(ct.counts)) {
    # print((j))
    k <- which(w$brain.ct == j)

    output$cpm[[j]] <- rowMeans(cpm[,k])
    output$rpkm[[j]] <- rowMeans(rpkm[,k])
  }

  output <- lapply(output, function(x) as.data.frame(do.call("cbind", x)))

  # add neurons, which come from pooling exc and inh cells
  neu <- which(w$brain.ct %in% c("Excitatory", "Inhibitory"))

  output$cpm$Neurons <- rowMeans(cpm[,neu])
  output$rpkm$Neurons <- rowMeans(rpkm[,neu])


  # expression threshold: a gene is kept if > 1 unit in at least 1 cell-type
  output <- lapply(output, function(x) {
    keep <- which(apply(x, 1, max) > 1)
    x <- x[keep,]
    return(x)
  })

  # return
  return(output)
}


run_dtg = function(exp, sig){

  common_genes = intersect(rownames(exp), rownames(sig))
  exp = exp[pmatch(common_genes, rownames(exp)),]
  sig = sig[pmatch(common_genes, rownames(sig)),]

  y = cbind(exp, sig)
  y = normalizeBetweenArrays(y)
  y = t(y)


  annot = colnames(sig) %>%
    as.data.frame() %>%
    set_colnames("Sample") %>%
    mutate(Cell_type = gsub("\\..*", "", Sample))

  of_interest = unique(annot$Sample)

  ps = lapply(1:length(of_interest), function(i) {
    which(annot$Sample == of_interest[i])
  })


  names(ps) = of_interest
  marker_list = find_markers(y,pure_samples=ps,data_type="rna-seq",marker_method='ratio')


  q = .1
  quantiles = lapply(marker_list$V,function(x)quantile(x,1-q))
  K = length(ps)
  n_markers = sapply(1:K,function(i){max(which(marker_list$V[[i]] > quantiles[[i]]))})


  marks = marker_list$L
  dc <- dtangle(y, pure_samples=ps, n_markers=n_markers, data_type = 'rna-seq', markers = marks)
  final_est <- dc$estimates[(dim(sig)[2]+1):dim(y)[1],]
  colnames(final_est) <-  of_interest


  return(final_est)

}


run_decon = function(m, s) {
  res <- as.data.frame(DeconRNASeq(m, s, use.scale = TRUE)$out.all)
  rownames(res) <- colnames(m)
  return(res)
}


## Expression matrix pre-processing functions (for variancePartition analysis)


## Thresholding for filtering
thresh <- 1
thresh.in.weak <- 0.1
thresh.in.stringent <- 0.2

apply.threshold <- function(data, t = thresh, fraction = thresh.in.weak) {
  logi <- data > t
  keep <- (rowSums(logi) / ncol(logi)) > fraction

  data <- data[keep,]
  return(data)
}


thresh <- function(x) {
  y <- x > 1
  keep <- rowSums(y) > (ncol(y) / 10)
  return(x[keep,])
}


read_expr <- function(path, dataset_id) {
  x <- read.csv(path, check.names = FALSE, row.names = 1)

  if (dataset_id == "HDBR" && "EnsemblID" %in% colnames(x)) {
    x <- x %>% column_to_rownames("EnsemblID")
  }
  x
}







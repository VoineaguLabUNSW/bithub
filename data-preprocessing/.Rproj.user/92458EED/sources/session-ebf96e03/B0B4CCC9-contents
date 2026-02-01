source("../preprocess/functions.R")
source("utility_functions.R")
source("fun-cibersort.R")
load("/home/neuro/Documents/Brain_integrative_transcriptome/BITHub-preprocessing/data/signatures/sigsBrain.rda")
library(recount3)
library(magrittr)
library(tibble)
library(reshape2)
library(SummarizedExperiment)
library(corrplot)
library(dplyr)
library(ggvenn)
library(pander)
library(gridExtra)
library(variancePartition)
library(DT)
library(EnsDb.Hsapiens.v86)
library(singscore)
library(AnnotationHub)
library(stargazer)
library(ggfortify)
library(glue)
library(cowplot)
library(broom)
library(glmpca)
library(naniar)
library(DeconRNASeq)
library(dtangle)
library(e1071)
library(parallel)
library(preprocessCore)
library(Metrics)
library(DTWBI)


brain.dir =file.path("/home/neuro/Documents/BrainData/Bulk")
e <- list()

e$GTEx <- read.csv(file.path(brain.dir, "/GTEx/Formatted/GTEx-exp.csv"),
                   check.names = FALSE, row.names = 1)
e$PE <- read.csv(file.path(brain.dir, "/PsychEncode/Formatted/PsychEncode-exp.csv"),
                 row.names =1, check.names = FALSE)
e$BSpan <- read.csv(file.path(brain.dir, "/BrainSpan/Formatted/BrainSpan-exp.csv"),
                    check.names = FALSE, row.names = 1)
e$BSeq <- read.csv(file.path(brain.dir,"/Brainseq/Formatted/BrainSeq-exp.csv"),
                   check.names = FALSE, row.names = 1)

e$HDBR <- read.csv(file.path(brain.dir, "/HDBR/Formatted/HDBR-exp.csv"),
                   check.names = FALSE, row.names = 1)  %>%
  column_to_rownames("EnsemblID")

datasets = c("BSpan", "HDBR", "BSeq", "GTEx", "PE")

decon_results = list()

for(d in datasets){
  exp = e[[d]]

  message(paste("Now running deconvolution for", d))

  message(paste("Running deconRNASeq for", d))

  res.DRS = run.DRS(exp,sigsBrain$MB)

  decon_results[[paste0(d, "_", "DRS")]] = res.DRS

  message(paste("Running detangl for", d))

  res.dtg = run_dtg(exp , sigsBrain$MB)

  decon_results[[paste0(d, "_", "DTG")]] = res.dtg

  exp %<>%
    rownames_to_column("EnsID")

  message(paste("Running CIBERSORT for", d))

  res.cbs = CIBERSORT(sig_matrix = sigsBrain$MB, mixture_file = exp)
  decon_results[[paste0(d, "_", "CIBERSORT")]] = res.cbs

}

save(decon_results, file = "/home/neuro/Documents/Brain_integrative_transcriptome/BITHub-preprocessing/output/Results/Deconvolution/decon-estimates.Rda")

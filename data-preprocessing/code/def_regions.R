############## Defining structures #####################
structure_acronym = list()

structure_acronym[["AMY"]] = c("Brain - Amygdala")
structure_acronym[["CB"]] = c("Brain - Cerebellum", "cerebellum")
structure_acronym[["HYP"]] = c("Brain - Hypothalamus")
structure_acronym[["SNA"]] = c("Brain - Substantia nigra")
structure_acronym[["ACC"]] = c("Brain - Anterior cingulate cortex (BA24)")
structure_acronym[["CTX"]] = c("Brain - Cortex", "cerebral cortex")
structure_acronym[["NAC"]] = c("Brain - Nucleus accumbens (basal ganglia)")
structure_acronym[["CAU"]] = c("Brain - Caudate (basal ganglia)", "basal ganglion")
structure_acronym[["DLPFC"]] = c("Brain - Frontal Cortex (BA9)")
structure_acronym[["PUT"]] = c("Brain - Putamen (basal ganglia)")
structure_acronym[["CBC"]] = c("Brain - Cerebellar Hemisphere")
structure_acronym[["HIP"]] = c("Brain - Hippocampus", "hippocampus")
structure_acronym[["SCI"]] = c("Brain - Spinal cord (cervical c-1)", "spinal cord")
structure_acronym[["TCx"]] = c("temporal lobe")

structure_acronym[["MEDU"]] = c("medulla oblongata")
structure_acronym[["PONS"]] = c("pons")
structure_acronym[["DIEN"]] = c("diencephalon")
structure_acronym[["BF"]] = c("brain fragment")
structure_acronym[["CP"]] = c("choroid plexus")
structure_acronym[["DIEN-MID"]] = c("diencephalon and midbrain")
structure_acronym[["FB"]] = c("forebrain")
structure_acronym[["FB-MID"]] = c("forebrain and midbrain")
structure_acronym[["FBF"]] = c("forebrain fragment")
structure_acronym[["HB"]] = c("hindbrain")
structure_acronym[["HBF"]] = c("hindbrain fragment")
structure_acronym[["HB/C"]] = c("hindbrain without cerebellum")
structure_acronym[["MB"]] = c("midbrain")
structure_acronym[["PIT-DIEN"]] =c("pituitary and diencephalon")
structure_acronym[["TEL"]] = c("telencephalon")



################### Defining regions ####################
regions = list()

regions[["Subcortex"]] = c("AMY", "CGE", "DTH", "HIP", "LGE", "MD", "CAU",
                           "STR", "SNA", "PUT", "HYP", "NAC")

regions[["Cortex"]] = c("A1C", "DLPFC", "IPC", "ITC", "M1C",
                        "M1C-S1C", "ACC", "MGE", "Ocx", "OFC",
                        "PCx", "S1C", "STC","TCx", "V1C", "VFC",
                        "CTX", "MTG", "M1lm", "M1ul","CgG",
                        "S1ul","S1lm", "MFC")

regions[["Cerebellum"]] = c("CBC", "CB", "URL")

regions[["Spinal Cord"]] = c("SCI")



#regions[["Forebrain"]] = c("FB", "FBF", "DIEN", "PIT-DIEN", "TEL")
#regions[["Midbrain"]] =
#regions[["Hindbrain"]] =

### Regions for HDBR

regions_fetal = list()

regions_fetal[["Forebrain"]] = c("FB", "FBF", "DIEN", "PIT-DIEN", "TEL",
                                 "CTX", "TCx", "CGE", "HIP", "CAU")
regions_fetal[["Midbrain"]] = c("MB")
regions_fetal[["Hindbrain"]] = c("HB", "HBF", "HB/C",
                                 "CB", "MEDU", "PONS")
regions_fetal[["Brain"]] =c("BF",  "FB-MID", "DIEN-MID")
regions_fetal[["Chroid plexus"]] = c("CP")
regions_fetal[["Spinal Cord"]] = c("SCI")

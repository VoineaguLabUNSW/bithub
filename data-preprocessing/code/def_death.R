### Death cause


death_cause=list()

death_cause[["Suicide"]] = c("SUIC:ASPHYXIA", "SUIC:HIT BY TRAIN", "SUIC:GSW",
                             "SUIC:JUMPED", "SUIC:OD", "Suicide", "SUIC:BURNED",
                             "SUIC:DROWNED", "SUIC:HANGING", "SUIC:INHALED HELIUM",
                             "SUIC:MVA", "SUIC:STABBED", "Suicide, hanging",
                             "Asphyxia by hanging", "SUIC:CO")
death_cause[["Unknown"]] =c("Unknown", "UNDETERMINED", "UNKNOWN", "", "Other", "Unresponsive in bed")

death_cause[["Cancer"]] = c("Cancer", "Cancer (lung)", "Cancer (colon)",
                            "throat cancer", "stomach cancer",
                            "ovarian cancer", "Pancreatic Cancer",
                            "lung cancer", "metastic bladder cancer",
                            "Non-brain cancer", "adenocarcinoma of right lung",
                            "endometrial cancer")

death_cause[["Accident"]] = c("TRAUMA--INTERNAL BLEEDING", "Sudden Unexpected Death",
                              "sudden accident/abdominal trauma", "Drowning",
                              "DROWNING", "Motorcycle accident", "Motor vehicle accident",
                              "Multiple injuries", "OD", "accident, multiple injuries ",
                              "STRANGULATION", "sudden artrial fibrillation/fatal collapse",
                              "Airway obstruction", "Anoxic Encephalopathy", "ASPHYXIA",
                              "Asphyxia", "Aspiration", "aspiration of gastral material",
                              "Blunt head injury, hit by a car while walking",
                              "Commotio Cordis", "Drowning", "DROWNING", "FALL", "Head Trauma", "hypoxic ishaemic damage",
                              "Toxic shock syndrome", "Sudural hemorrhage", "Seizure Suspected", "MVA", "Accident", "Homicide", "SUBARACHNOID HEMORRHAGE")

death_cause[["Illness"]] =c("ACUTE PANCREAT",
                            "Acute Hemorrhagic Tracheobronchitis",
                            "acute necrotic pancreatitis",
                            "acute pancreatitis", "Respiratory arrest",
                            "Seizure Disorder", "Severe obesity/Bronchopneumonia",
                            "pulmonary fibrosis", "Multisystem Failure", "Diabetic Ketoacidosis",
                            "bronchopneumonia", "Asthma", "ASTHMA", "bronchopneumonia",
                            "chronic obstructive pulmonary disease",
                            "CIRRHOSIS","Complications Of Pseuodmyxoma Peritonei","COPD",
                            "Diabetic Ketoacidosis", "epilepsy", "Gastrointestinal Bleeding",
                            "Infection and parasitic disease", "SLEEP APNEA", "PNEUMONIA", "Pneumonia",
                            "EXHAUSTIVE MANIA/NMS", "GI HEMORRHAGE", "status epilepticus and myocardial infarct",
                            "Obstruction Of Bowel Due To Adhesion", "rheumatoid arthritis/Bells palsy")

death_cause[["Cardiac"]] =c("cardiac arrest due to inhalation of volatile arrythmogenic substances","CARDIAC",
                            "Cardiac Arrest", "Cardiac Arrhythmia", "Cardiac arrest", "Cardiac arrythmia",
                            "Cardiac arrhythmia due to conduction system", "Cardiac arrhytmia",
                            "Cardiac Tamponade","Cardiopulmonary Arrest", "Cardiovascular",
                            "congestive cardiac failure", "Congestive Heart Failure", "Heart Attack", "MYOCARDITIS",
                            "Arteriosclerotic cardiovascular disease",
                            "Hypertensive atherosclerotic cardiovascular disease, fall down stairs",
                            "Lymphocytic myocarditis", "myocardial infarction", "probable MI", "PULM EMBOL",
                            "Abdominal aortic anerysm", "Anomalous left coronary artery with complications")

death_cause[["Natural"]] =c("Natural", "Natural/epilepsy")

Coverage gaps without the reference layers - Best Documentation entry (Zindi user skaiea13)

BEST_DOCUMENTATION.pdf / .md / .html   the writeup (same text in all three)
src/                                    lbreg_features.py, lbreg_probe.py, lbreg_fit.py, edge_no_overture.py, and
                                        misfiled_stations.py, misfiled_report.py, common.py (classification deserts)
probes/lbreg_probes.json                a and public RMSE of the 27 single-predictor probes (Table 3)
outputs/                                joint13.csv (= submission FNBceCuK) and its coefficients, joint17.csv,
                                        joint17_w1.csv (joint17 with the no-Overture rule, = submission knE1GJ3o),
                                        joint21.csv/.json and joint21_w1.csv (= gki9K7jy, selected for private scoring),
                                        joint25.csv/.json and joint25_w1.csv (the values of 6BNL8pZ3, also selected),
                                        all rebuilt by the scripts
analysis/misfiled/classification_deserts.csv   input to the fire_classdesert predictor
third_party/overture-coverage-equity/   derived tract features by another participant, MIT, unchanged (SOURCE.txt)
LICENSE                                 MIT licence for our scripts and writeup (third_party/ keeps its own)
SHA256SUMS                              hashes of every file above

To reproduce, place the challenge data next to src/ as data/reference/<region>/ and data/strata/<region>/, then run
  python src/lbreg_features.py
  python src/lbreg_fit.py outputs/joint21.csv <the 21 predictors listed in outputs/joint21.json>
  python src/edge_no_overture.py outputs/joint21.csv outputs/joint21_w1.csv
The last command writes the file selected as gki9K7jy byte for byte. The same two commands with the 25 predictors of
outputs/joint25.json give the values of 6BNL8pZ3 (the uploaded file used CRLF line endings and wrote 1 for 1.0), and
Section 8 of the writeup also rebuilds FNBceCuK and knE1GJ3o. Requirements: Python 3 with pandas, NumPy and pyarrow;
the DuckDB command-line tool only if you rebuild analysis/misfiled/ with the misfiled_* scripts.

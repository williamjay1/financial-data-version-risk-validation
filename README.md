# Financial data version risk in bankruptcy model validation

Reproducibility package for the paper **Financial data version risk in bankruptcy model
validation: separating scoring, development and evaluation effects** by Junjie Zhang
(Shanghai International Studies University).

The paper asks how the choice of historical financial data version enters a model
validation result. A historical predictor can have several reported values, and a
chronological train and test split does not specify which version a development process
or a scoring exercise uses. The package contains a crossed version validation protocol
that holds observation identities, outcome labels, design weights and initial
missingness fixed while version selection varies separately at development and at
scoring, together with the frozen inputs and outputs of the bankruptcy application.

## Headline results

| Quantity | Value |
| --- | --- |
| Cohort | 5,502 annual filing windows, 188 directly linked bankruptcy registry events |
| Reported tuned difference (diagonal) | +2.839, +2.768, +1.766 average precision points across the three test blocks |
| Direct substitution contrast | -2.777, +1.367, +0.112 points |
| Redevelopment contrast | +4.945, +1.432, +1.901 points |
| Development domain experiment | holding the evaluation sample fixed, the contrast moved from +2.852 to -16.009 points |

## Layout

| Path | Contents |
| --- | --- |
| `manuscript/` | Final manuscript (PDF and Word), supplementary document, submission copies, five figures as SVG and vector PDF, six tables as CSV, and the LaTeX source |
| `code/datasets/` | Frozen derived analysis inputs: sampling frame, model cohort, version panel and source-corrected arms |
| `code/datasets_round2/` | Fit date reconstruction panels and the source verified correction panel |
| `code/scripts/` | Original analysis pipeline: sampling, version pairing, modelling and descriptive figures |
| `code/scripts_round1/`, `code/scripts_round2/` | Revision rounds: fit date reconstruction, development controls, evaluation diagnostics, source semantics and assembly |
| `code/scripts_final/` | Final round: publication figures with a layout audit, manuscript assembly with compliance gates, submission pack, PDF production and quality assurance |
| `results/round1/`, `results/round2/`, `results/final/` | Frozen metrics, four cell decompositions, audits, saved predictions and figures for each round |
| `docs/` | Data dictionary, environment lock, portable reproduction script, build reports and the submission requirement check |

## Reproducing the reported results

Every table and figure is regenerated from frozen outputs, so no reported number is
transcribed by hand.

```bash
# figures, including the layout audit that rejects any text collision
python code/scripts_final/build_figures_publication.py

# tables and main text, including the compliance gates
python code/scripts_final/assemble_manuscript.py

# Word deliverables and the PDF reading copy
python code/scripts_final/build_deliverables.py
python code/scripts_final/build_pdf_reading_copy.py
python code/scripts_final/pdf_qa.py

# submission pack
python code/scripts_final/build_submission_pack.py
python code/scripts_final/build_title_page.py
python code/scripts_final/build_submission_supplement.py
python code/scripts_final/build_submission_readme.py
python code/scripts_final/submission_final_check.py
```

The scripts were written for the frozen directory layout of the working tree, so paths
inside them are relative to the parent of the round folders. `docs/reproduce.py` and
`docs/portable_validation.md` record the portable smoke test that recomputes the four
cell metrics from the saved predictions.

## Environment

`docs/environment.json` records the interpreter and package versions, and
`docs/requirements-lock.txt` pins the direct dependencies. The analysis uses public
data only: SEC EDGAR filings through the official submissions and company facts
interfaces, the Florida-UCLA-LoPucki Bankruptcy Research Database event list, and
consumer price index series from the US Bureau of Labor Statistics.

## What is not included

Raw downloaded filings and API caches are excluded, because redistribution is governed
by the source terms and the files are large; archived record roots are shown as
placeholders in the few lineage files that reference them. Fitted model binaries
(`*.joblib`) are excluded, and every model is reproducible from the scripts and the
frozen inputs. Intermediate packaging archives are excluded as well.

## Evidence levels used in the paper

Three levels are kept apart throughout: agreement with a displayed statement,
authentication of the original issuer XBRL context, and the current recorded value. No
original issuer context was authenticated, so a difference that agrees with a displayed
statement is reported as a supported measurement rather than a certified correction.

## Citation

Please cite the paper and this package, as described in `CITATION.cff`.

## Licence

Code is released under the MIT licence. Text, figures and derived data are released
under CC BY 4.0. See `LICENSE`.

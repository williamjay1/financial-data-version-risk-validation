# Financial data versions: second-round reproducibility handover

This is a local research handover, not a public data release or a license to redistribute underlying registry or filing data. Keep the extracted `study/` layout intact. No upload, DOI or journal submission is performed.

## One offline command

Use Python 3.12 and an environment with the pinned dependencies. From `study/`:

```text
python -m pip install -r revision_20260922_round2/reproducibility/requirements-lock.txt
python revision_20260922_round2/reproducibility/reproduce.py
```

Dependency installation is separate and may require internet access. Once installed, the reproduction command needs no network or excluded raw archive. It uses relative paths; `--project` and `--output-dir` can select another authorized location. On the original computer, all computation stays on D: under its storage policy.

The command verifies package hashes and frozen input identity, checks fit-date cutoffs/A scoring inputs and the 22-context scale-only sensitivity, recomputes weighted AP/Brier/ROC and tied-capacity recall from saved predictions, and writes new four-cell tables. It also re-evaluates all 200 saved paired refitting predictions under development-only, evaluation-only and joint weights, rebuilding their summaries; the original four-cell and 1,000-draw conditional calculations are recomputed. Outputs go to `revision_20260922_round2/reproduced/`. Archived files are not overwritten.

**This recalculates metrics and summaries from saved predictions; it does not generate new model predictions or retrain models. No model is fitted by the command.** The included `build_main_displays.py` and `assemble_main.py` regenerate the four figures (PNG/PDF/SVG), main tables, bibliography and Markdown manuscript under `reproduced/`; `build_supplement.py` also rebuilds the supplementary tables and Markdown. A narrow adapter redirects only output-path assignments; numerical formulas and frozen scripts are unchanged. Rebuilt main and supplementary manuscripts, main table JSON and bibliography must equal the packaged versions byte for byte. Word rendering is a separate delivery task and is not performed by this command. `--skip-manuscript` runs only the analytical checks and recalculation.

## What the directories mean

- Root `datasets/`, `scripts/`, `results/`: frozen original cohort, facts, sample design and original analytical records.
- `revision_20260922/`: earlier fitted models, paired predictions and the completed 200-draw refitting analysis. These are historical inputs to the current analysis.
- `revision_20260922_round2/`: current controls, fit-date reconstruction, scale-only sensitivity, source semantics, evaluation diagnostics and current manuscript.
- `SOURCE_ACCESS_AND_EXCLUSIONS.json`: source routes, omissions and redistribution boundaries.
- `PACKAGE_MANIFEST.json`: hashes of actual packaged files, source hashes and redaction transformations. Historical manifest paths/hashes remain provenance; use the package hash for a redacted file.

The validation report for this exact ZIP is supplied separately after extraction and execution. It records the ZIP hash and is deliberately outside the ZIP to avoid circular hashing. Earlier DRAFT package reports and superseded page-rendering checks are excluded. Historical analytical manifests inside the package describe their own named frozen runs; they are not substitutes for the current package validation.

## Training and raw-source reconstruction

The package retains fitted artifacts and execution code, but the default entry does not claim to rebuild every model or source cache. Complete source reconstruction needs the excluded lawfully acquired SEC/BRD archives and original cache routing. Some historical execution modules also enforce original project bindings or absolute paths. Do not run every archived script indiscriminately or interpret a missing raw cache as a failed offline prediction audit.

A portable optional refit of the original frozen A/B fixed or tuned models is available through the previous round's explicit training entry:

```text
python revision_20260922/reproducibility/reproduce.py --verify-only --retrain fixed --output-dir revision_20260922_round2/optional_refit_fixed
```

This makes new LR/LightGBM fits on the frozen original cohort. It is separate from the round-two offline command and does not rerun all controls or the full 200-draw pipeline. Two CPU threads are used. No new training is represented by the package validation report unless explicitly stated there.

## Interpretation and source boundaries

The current supported correction diagnostic is **22 scale contexts**. The four earlier sign corrections remain unresolved pending concept/context and author verification; the historical 26-context sensitivity is retained as historical/disputed evidence, not the current supported correction set. Selected filing-display support is not authenticated original XBRL or an archived API snapshot.

The labels concern directly linked BRD events, not every legal bankruptcy. Fit-date reconstruction constrains selected disclosures before fitting; A test inputs remain tied to each original accession. Most later training disclosures were already available before fitting and cannot all be described as future information relative to that time. Size domains are proxies, not exact registry eligibility.

All additional analyses are post hoc relative to earlier test results. Matching repetitions, four common parameter configurations, and dependent perturbation modes are sensitivity diagnostics, not independent new populations or additive variance components. The three perturbation modes are recomputed without claiming new training or new confidence intervals.

Third-party full texts, HTML/XML, large raw SEC caches, internal Word-rendering PDF/PNG and superseded exploratory runs are excluded. Audit metadata retains required identifiers, numeric amounts, locators, URLs and hashes, while excerpt columns are omitted where necessary. Check source terms and permissions before any public redistribution; this package grants no rights over third-party or derived data.

"""Create a local, hash-indexed analysis package. Never upload or include raw archives."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import zipfile

ROOT=Path(__file__).resolve().parents[1]

def digest(p):
    h=hashlib.sha256()
    with p.open('rb') as f:
        for b in iter(lambda:f.read(2**20),b''):h.update(b)
    return h.hexdigest()

def main():
    if ROOT.drive.lower()!='d:':raise ValueError('Working outputs belong on D:')
    run=json.loads((ROOT/'results/final_run_index.json').read_text(encoding='utf-8'))
    paths=[]
    names=['build_vintage_panel','prepare_model_cohort','final_data_gate','freeze_analysis_protocol',
           'lock_sampling_frame','run_vintage_models','uncertainty_vintage','build_vintage_figures',
           'build_sensitivity_cohorts','package_study','assemble_manuscript','make_manuscript_docx','expanded_sec_fetch',
           'control_sec_fetch','universe_build','universe_finalize','universe_download_hf','finalize_delivery_audit']
    paths += [ROOT/'scripts'/f'{n}.py' for n in names]
    names=['sampling_frame','model_cohort','vintage_facts','vintage_panel',
           'universe_annual_filings_2010_2021','sensitivity_source_scale_corrected','sensitivity_no_transition']
    paths += [ROOT/'datasets'/f'{n}.parquet' for n in names]
    paths += [ROOT/'phase2_protocol.json',ROOT/'manuscript/references.bib',ROOT/'manuscript/manuscript.md',ROOT/'manuscript/front_methods.md',ROOT/'manuscript/source_examples.md',
              ROOT/'manuscript/Financial_Vintage_Registry_Prediction_Manuscript.docx',ROOT/'manuscript/投稿与使用说明.md',
              ROOT/'manuscript/literature_map.md',ROOT/'manuscript/venue_notes.md']
    for glob in ['cohort_*','sampling_frame_summary.json','final_data_gate.json','sensitivity_design.json',
                 'final_run_index.json','ARTICLE_BUILD_SPEC.md','manuscript_*','final_*audit*','final_interpretation_review.md','word_visual_qa*',
                 'control_sec_*manifest*.jsonl','control_sec_summary*.json','expanded_sec_*manifest*.jsonl',
                 'corporate_access_manifest*.json','universe_artifact_manifest.json','universe_sraf_count_crosscheck.csv']:
        paths += [p for p in (ROOT/'results').glob(glob) if p.is_file()]
    for entry in run['model_runs']:
        manifest=Path(entry['manifest'])
        prefix=manifest.name.removesuffix('_manifest.json')
        paths += [p for p in manifest.parent.glob(prefix+'*') if p.is_file()]
    for entry in run['uncertainty_runs']:
        manifest=Path(entry['manifest'])
        prefix=manifest.name.removesuffix('_manifest.json')
        paths += [p for p in manifest.parent.glob(prefix+'*') if p.is_file()]
    figure_dir=Path(run['figure_directory'])
    paths += [p for p in figure_dir.iterdir() if p.is_file()]
    paths += [p for p in (ROOT/'results').glob('descriptive_'+figure_dir.name+'*') if p.is_file()]
    # The complete BRD download and SEC JSON originals remain in E:; the
    # local analysis subset is not an assertion of public redistribution rights.
    paths=sorted(set(p for p in paths if p.exists()))
    required=[ROOT/'manuscript/Financial_Vintage_Registry_Prediction_Manuscript.docx',ROOT/'datasets/model_cohort.parquet']
    if any(p not in paths for p in required):raise ValueError('Final manuscript/cohort missing')
    versions={p:importlib.metadata.version(p) for p in ['numpy','pandas','scipy','scikit-learn','lightgbm','pyarrow','joblib','matplotlib']}
    readme='''# Financial statement vintage study: local analysis package

This package accompanies the complete research manuscript. It is a local handover,
not a public data release or a claim of permission to redistribute original sources.
SEC JSON, the original BRD download, source statements and third-party master-index
archives remain in the immutable E: raw repository and are not bundled here.

## What is reproducible

The package includes the frozen paired cohort, fact lineage, locked sampling frame,
training code, fitted models, row-level held-out predictions, selected hyperparameters,
conditional sampling-design intervals, both specified sensitivities, and figure data.
results/final_run_index.json identifies the exact runs used in the manuscript.
PACKAGE_MANIFEST.json checksums every included file. The manuscript is anonymous.

## Run on D:

Use Python 3.12 and the versions in requirements-analysis.txt. Keep working files,
caches and outputs on D:. The scripts infer their project root from their location.
From the original study root, the main analysis commands are:

    python scripts/run_vintage_models.py --dry-run
    python scripts/run_vintage_models.py --run --threads 4
    python scripts/uncertainty_vintage.py --run --predictions results/<run>_test_predictions.parquet
    python scripts/uncertainty_vintage.py --run --predictions results/<run>_frozen_a_predictions.parquet --analysis-mode frozen_A_inputs
    python scripts/build_sensitivity_cohorts.py --build

For sensitivity fits use --input datasets/sensitivity_source_scale_corrected.parquet
or --input datasets/sensitivity_no_transition.parquet and a distinct --output-dir under results.
The training guard binds source hashes to the successful data gate and sensitivity
design. Sensitivity records retain original local provenance paths; after relocation,
regenerate sensitivity_design.json with the build command before sensitivity fitting.
The main analysis remains bound to the same frozen input hashes. Do not silently
edit hashes to bypass an audit failure. Rebuilding the original data gate requires
the original E: raw sources and D: SEC working cache, which are not included here.

The figure module help describes explicit model and uncertainty manifests. Existing
model manifests preserve original absolute paths, including the frozen-A prediction
file used by the figure builder. To regenerate figures after moving the package to a
different D: directory, first rerun models and uncertainty and supply the new manifests.
Direct figure regeneration from the archived original manifests still requires their
recorded original paths. The included final figures can be viewed without rerunning.
Formal
intervals use 1,000 paired rescaled cluster replicates with seed 20260921. They hold
models and registry cases fixed; they are not full predictive-generalization intervals.
Version B contains later disclosures and is a diagnostic, not a live prediction model.

No class balancing, synthetic minority observations, test-driven grid changes or
omission of unfavorable test blocks is part of the analysis. Source-verified scale
correction and transition-report exclusion are separately identified sensitivity runs.
Some financial tags are unavailable; the restricted accessible-data domain must be
retained when describing results. Outcome zero means no directly linked first BRD
event in the 365-day window, not a verified absence of all legal bankruptcy events.

## Source reconstruction

Source manifests record URLs, retrieval times, immutable E: filenames and hashes.
Historical-frame and SEC extraction scripts document construction. Network access
is not required to rerun model evaluation from the derived cohort. Full source
reconstruction requires the original documented input repositories and their access
conditions; public download access does not establish unrestricted re-release rights.
No automatic upload, journal submission or external contact is performed by this package.
'''
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=ROOT/'manuscript'/f'Financial_Vintage_Reproducibility_{stamp}.zip'
    manifest={'created_utc':stamp,'scope':'local analysis handover; excludes raw original archives',
              'files':[{'path':p.relative_to(ROOT).as_posix(),'sha256':digest(p),'bytes':p.stat().st_size} for p in paths],
              'versions':versions,'script_sha256':digest(Path(__file__))}
    with zipfile.ZipFile(target,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in paths:z.write(p,p.relative_to(ROOT).as_posix())
        z.writestr('README.md',readme)
        z.writestr('requirements-analysis.txt','\n'.join(f'{p}=={v}' for p,v in versions.items())+'\n')
        z.writestr('PACKAGE_MANIFEST.json',json.dumps(manifest,indent=2))
    with zipfile.ZipFile(target) as z:
        assert z.testzip() is None
        for item in manifest['files']:
            assert hashlib.sha256(z.read(item['path'])).hexdigest()==item['sha256']
    report={'path':str(target),'sha256':digest(target),'bytes':target.stat().st_size,'verified_files':len(paths),'zip_crc':'PASS','all_embedded_hashes':'PASS'}
    (ROOT/'results/package_audit.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()

"""Fixed-configuration cap experiments reusing the identical fitted A anchors."""
from pathlib import Path
import os
for var in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[var]='2'
import json
import joblib
import pandas as pd
import revision_models as rm

REV=Path(__file__).resolve().parents[1]

def main():
    audit=json.loads((REV/'results/version_caps/audit.json').read_text())
    assert audit['status']=='PASS'
    source_manifest=REV/'results/version_caps/manifest.json'
    m=json.loads(source_manifest.read_text())
    assert m['source_reconstruction_matches']==11004
    anchors={(f'{a}_{b}',model):joblib.load(REV/'results/models/artifacts'/f'fixed_full__{a}_{b}__A__{model}.joblib')
             for a,b in rm.base.BLOCKS for model in ['LR','LGBM']}
    for cap in [90,365,730]:
        source=REV/f'datasets/cap_{cap}.parquet'
        assert rm.base.sha256(source)==m['outputs'][str(cap)]['sha256']
        df=rm.base.validate_cohort(pd.read_parquet(source))
        out=REV/f'results/cap_models/{cap}'
        out.mkdir(parents=True,exist_ok=True)
        rm.run_fixed_cohort(df,out,f'cap_{cap}',anchor_bundles=anchors)
        rm.base.write_json(out/'cap_run_manifest.json',{
            'status':'complete','cap_days':cap,'source_sha256':rm.base.sha256(source),
            'version_construction_manifest_sha256':rm.base.sha256(source_manifest),
            'script_sha256':rm.base.sha256(Path(__file__)),
            'model_module_sha256':rm.base.sha256(Path(rm.__file__)),
            'A_anchors_reused':6,'B_fits':6,'interpretation':'Fixed hyperparameters, paired retrospective version availability sensitivity',
            'outputs':{p.name:rm.base.sha256(p) for p in out.iterdir() if p.is_file()}})
        print(json.dumps({'cap':cap,'status':'complete'}),flush=True)

if __name__=='__main__':main()

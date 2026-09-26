"""Restrict display-supported adjustment to Nobilis scale contexts; exclude sign disputes."""
from pathlib import Path
import os
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='2'
import sys
sys.dont_write_bytecode=True
import json
from datetime import datetime,timezone
import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score,roc_auc_score

REV=Path(__file__).resolve().parents[1]
ROOT=REV.parent
sys.path.insert(0,str(ROOT/'revision_20260922/scripts'))
import source_corrected_models as sc

def run():
    sc.REV=REV
    sc.OUT=REV/'results/scale_only'
    sc.DATA=REV/'datasets'
    sc.SUFFIX='_scale_only'
    sc.VERSION=2
    sc.CORRECTIONS=REV/'results/source_semantics/scale_supported_corrections.csv'
    corrections=pd.read_csv(sc.CORRECTIONS,dtype={'cik':str},keep_default_na=False)
    assert len(corrections)==22
    sc.OUT.mkdir(parents=True,exist_ok=True)
    sc.mod.base.write_json(sc.OUT/'scope_plan.json',{
        'created_utc':datetime.now(timezone.utc).isoformat(),'status':'frozen_before_fitting',
        'correction_key_count':22,'source':str(sc.CORRECTIONS),'source_sha256':sc.mod.base.sha256(sc.CORRECTIONS),
        'meaning':'Display-supported common scale adjustment, not human or original-XBRL certification',
        'excluded':'Four sign-disputed contexts are not applied; prior 26-context analysis is a separate disputed sensitivity',
        'expected_structure':'Two A/B log_assets cells change; common bundle scaling cancels within nine financial ratios',
        'base_engine_sha256':sc.mod.base.sha256(sc.__file__),'wrapper_sha256':sc.mod.base.sha256(__file__)})
    sc.run()
    p=pd.read_parquet(sc.OUT/'predictions.parquet');m=pd.read_csv(sc.OUT/'metrics.csv')
    errors=[]
    for _,row in m.iterrows():
        g=p.loc[(p.experiment==row.experiment)&(p.block==row.block)&(p.model==row.model)&
                (p.train_version==row.train_version)&(p.score_version==row.score_version)]
        y=g.registry_event_365.to_numpy();w=g.sample_weight.to_numpy();pred=g.prediction.to_numpy()
        values={'average_precision':average_precision_score(y,pred,sample_weight=w),
                'brier':np.average((y-pred)**2,weights=w),'roc_auc':roc_auc_score(y,pred,sample_weight=w)}
        errors.extend(abs(value-row[key]) for key,value in values.items())
    changes=pd.read_csv(sc.OUT/'changed_features.csv')
    ab=changes.loc[changes.arm.isin(['A','B'])]
    assert len(ab)==2 and set(ab.feature)=={'log_assets'}
    assert max(errors)<1e-12
    sc.mod.base.write_json(sc.OUT/'independent_audit.json',{'status':'PASS','metric_cells':len(errors),
        'max_metric_difference':max(errors),'ab_changed_feature_cells':len(ab),
        'ab_features':ab.to_dict('records'),'sign_disputes_applied':False,
        'scope':'Independent metric formulas from stored predictions; not independent raw-XBRL measurement'})
    print(json.dumps({'status':'PASS','metric_cells':len(errors),'ab_changed_cells':len(ab)}),flush=True)

if __name__=='__main__':run()

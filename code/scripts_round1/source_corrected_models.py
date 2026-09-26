"""Exact-context display/API corrections; post hoc diagnostics, not source certification."""
from pathlib import Path
import sys
sys.dont_write_bytecode=True
import argparse, importlib.util, json, math
from datetime import datetime, timezone
import numpy as np
import pandas as pd

HERE=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('revision_models_readonly',HERE/'revision_models.py')
mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
ROOT=mod.ROOT; REV=mod.REVISION; OUT=REV/'results/corrected_models'; DATA=REV/'datasets'
VERSION=1
SUFFIX=''
FACTS=ROOT/'datasets/vintage_facts.parquet'; CORRECTIONS=REV/'results/source_audit/verified_corrections.csv'
FACT_HASH='18f5f0424091c17bb80fa146d55890a849c1fce97f3f0f0d0e784d7422c71c5f'
COMPONENTS=['assets','liabilities','equity','cash','current_assets','current_liabilities','net_income','revenue','operating_income','operating_cash','retained_earnings']

def ratios(v):
    a=v['assets']; valid=np.isfinite(a) and a>0
    r={'log_assets':math.log(a) if valid else np.nan}
    for key in ['liabilities','equity','cash','net_income','revenue','operating_income','operating_cash','retained_earnings']:
        r[key+'_to_assets']=v[key]/a if valid else np.nan
    r['working_capital_to_assets']=(v['current_assets']-v['current_liabilities'])/a if valid else np.nan
    return r

def reconstruct(cohort,facts):
    groups={(str(cik),str(acc)):g for (cik,acc),g in facts.groupby(['cik','original_accession'],sort=False)}
    result={arm:[] for arm in ['A','B','C']}
    for row in cohort[['cik','accession']].itertuples(index=False):
        g=groups[(str(row.cik),str(row.accession))]
        mod.base.require(not g.feature.duplicated().any(),'Duplicate selected component in facts')
        for arm in result:
            v={f:np.nan for f in COMPONENTS}; v.update(dict(zip(g.feature,g[arm])))
            computed=ratios(v); result[arm].append([computed[f] for f in mod.base.FEATURES])
    return {arm:np.asarray(values) for arm,values in result.items()}

def match_mask(facts,row,arm):
    col={'A':'accn','B':'B_accession','C':'C_accession'}[arm]
    accession=facts[col].fillna('').where(facts[col].fillna('').ne(''),facts.accn)
    return (facts.cik.eq(row['cik'])&accession.eq(row['source_accession'])&facts.tag.eq(row['tag'])&
            facts.start.fillna('').eq(row['start'])&facts.end.eq(row['end'])&facts.unit.eq(row['unit']))

def self_test():
    v={f:float(i+2) for i,f in enumerate(COMPONENTS)}; before=ratios(v); after=ratios({f:x*1000 for f,x in v.items()})
    assert abs(after['log_assets']-before['log_assets']-math.log(1000))<1e-12
    assert all(abs(after[f]-before[f])<1e-12 for f in mod.base.FEATURES if f!='log_assets')
    toy=pd.DataFrame([dict(cik='1',accn='x',B_accession='x',C_accession='x',tag='Assets',start='',end='2015-12-31',unit='USD'),
                      dict(cik='1',accn='x',B_accession='x',C_accession='x',tag='Assets',start='',end='2014-12-31',unit='USD')])
    row=dict(cik='1',source_accession='x',tag='Assets',start='',end='2015-12-31',unit='USD')
    assert match_mask(toy,row,'B').tolist()==[True,False]
    return {'uniform_scale_preserves_nine_ratios':True,'wrong_period_cannot_match':True}

def run():
    OUT.mkdir(parents=True,exist_ok=True); DATA.mkdir(exist_ok=True)
    mod.base.require(not (OUT/'manifest.json').exists(),'Refuse to overwrite completed correction analysis')
    df,binding=mod.load_base(); cohort=pd.read_parquet(ROOT/'datasets/model_cohort.parquet')
    mod.base.require(mod.base.sha256(FACTS)==FACT_HASH,'Frozen fact table hash mismatch')
    facts=pd.read_parquet(FACTS); corrections=pd.read_csv(CORRECTIONS,dtype={'cik':str},keep_default_na=False)
    keycols=['cik','source_accession','tag','start','end','unit']
    mod.base.require(not corrections.duplicated(keycols).any(),'Duplicate/conflicting correction keys')
    design={'recorded_utc':datetime.now(timezone.utc).isoformat(),'analysis_status':'post_hoc_revision',
            'source_main_sha256':mod.EXPECTED_HASH,'source_facts_sha256':FACT_HASH,'correction_csv_sha256':mod.base.sha256(CORRECTIONS),
            'correction_count':len(corrections),'scope':'Only exact CIK/accession/tag/start/end/unit plus existing API value; A/B/C independently; absence of later accession resolves to original A accession',
            'evidence_status':'Visible filing display/API discrepancy, not human or original XBRL certification',
            'models':['source_corrected_tuned original four-candidate independent single-year tuning','source_corrected_fixed declared LR C1 and LGBM7/30'],
            'held_fixed':'All row IDs, dates, labels, sampling weights, missingness and temporal splits; only verified raw components recomputed into all ten features',
            'no_extrapolation':'A correction for FY2015 cannot correct FY2014 even in the same source accession',
            'version':VERSION,'script_sha256':mod.base.sha256(__file__),'tests':self_test()}
    mod.base.require(not (OUT/'design.json').exists(),'Existing correction design needs explicit review before another run')
    mod.base.write_json(OUT/'design.json',design)
    (OUT/'verified_corrections_snapshot.csv').write_bytes(CORRECTIONS.read_bytes())
    before=reconstruct(cohort,facts); baseline_errors={}
    for arm,values in before.items():
        stored=cohort[[arm+'_'+f for f in mod.base.FEATURES]].to_numpy(dtype=float)
        mod.base.require(np.array_equal(np.isnan(stored),np.isnan(values)),f'Original {arm} mask reconstruction mismatch')
        delta=np.abs(stored-values); maxdiff=float(np.nanmax(delta)); baseline_errors[arm]=maxdiff
        mod.base.require(np.allclose(stored,values,rtol=0,atol=1e-12,equal_nan=True),f'Original {arm} ratio reconstruction mismatch')
    updated=facts.copy(); changes=[]; matching=[]
    for correction in corrections.to_dict('records'):
        hits=0
        for arm in ['A','B','C']:
            mask=match_mask(facts,correction,arm); ids=facts.index[mask]
            for idx in ids:
                old=float(facts.at[idx,arm]); expected=float(correction['api_value'])
                mod.base.require(old==expected,f'API value differs from exact correction key {correction["audit_id"]}/{arm}')
                new=float(correction['display_normalized_value']); mod.base.require(np.isfinite(new),'Nonfinite display correction')
                updated.at[idx,arm]=new; hits+=1
                changes.append({'audit_id':correction['audit_id'],'fact_row':int(idx),'cik':facts.at[idx,'cik'],
                                'original_accession':facts.at[idx,'original_accession'],'arm':arm,'feature':facts.at[idx,'feature'],
                                'tag':facts.at[idx,'tag'],'start':facts.at[idx,'start'],'end':facts.at[idx,'end'],
                                'source_accession':correction['source_accession'],'unit':correction['unit'],'old_api_value':old,'display_normalized_value':new})
        mod.base.require(hits>0,f'Correction has no exact facts match: {correction["audit_id"]}/{correction["tag"]}')
        matching.append({'audit_id':correction['audit_id'],'tag':correction['tag'],'start':correction['start'],'end':correction['end'],'hits':hits})
    after=reconstruct(cohort,updated); corrected=cohort.copy(); feature_changes=[]
    for arm,newvalues in after.items():
        cols=[arm+'_'+f for f in mod.base.FEATURES]; oldvalues=cohort[cols].to_numpy(dtype=float)
        mod.base.require(np.array_equal(np.isnan(oldvalues),np.isnan(newvalues)),f'{arm} correction altered mask')
        # Preserve untouched original binary values; all ten features are recomputed
        # only for an arm whose underlying selected components were verified changed.
        affected={(x['cik'],x['original_accession']) for x in changes if x['arm']==arm}
        selected=np.array([(str(c),str(a)) in affected for c,a in zip(cohort.cik,cohort.accession)])
        replacement=oldvalues.copy(); replacement[selected]=newvalues[selected]
        corrected[cols]=replacement
        for i,j in zip(*np.where(~np.isclose(replacement,oldvalues,rtol=0,atol=1e-12,equal_nan=True))):
            feature_changes.append({'cik':cohort.iloc[i].cik,'accession':cohort.iloc[i].accession,'arm':arm,'feature':mod.base.FEATURES[j],
                                    'old':oldvalues[i,j],'new':replacement[i,j]})
        mod.base.require(np.array_equal(replacement[~selected],oldvalues[~selected],equal_nan=True),'Unaffected features changed')
    excluded=[arm+'_'+f for arm in ['A','B','C'] for f in mod.base.FEATURES]
    pd.testing.assert_frame_equal(cohort.drop(columns=excluded),corrected.drop(columns=excluded),check_exact=True)
    path=DATA/f'source_verified_corrected{SUFFIX}.parquet'; mod.base.require(not path.exists(),'Corrected dataset already exists')
    corrected.to_parquet(path,index=False); updated.to_parquet(DATA/f'source_verified_corrected_facts{SUFFIX}.parquet',index=False)
    pd.DataFrame(changes).to_csv(OUT/'applied_fact_changes.csv',index=False)
    pd.DataFrame(feature_changes).to_csv(OUT/'changed_features.csv',index=False)
    audit={'status':'PASS','baseline_reconstruction_max_absolute_error':baseline_errors,'correction_matches':matching,
           'applied_arm_fact_cells':len(changes),'changed_feature_cells':len(feature_changes),'affected_row_ids':len({(x['cik'],x['accession']) for x in feature_changes}),
           'changed_features_by_arm':pd.DataFrame(feature_changes).groupby('arm').size().to_dict(),
           'unchanged_metadata_labels_weights_rows':True,'all_arm_masks_unchanged':True,
           'dataset_path':str(path),'dataset_sha256':mod.base.sha256(path),
           'source_scope_note':'Every period must be independently listed. Version 2 adds eleven exact FY2014 comparative facts verified from the same 2016 filing display.' if VERSION==2 else 'FY2014 Nobilis comparative facts remain unchanged unless independently listed in this exact-context correction table.'}
    mod.base.write_json(OUT/'data_audit.json',audit)
    newdf=mod.base.validate_cohort(corrected); rec=mod.Recorder(OUT)
    print('START source_corrected_tuned',flush=True); mod.run_tuned(newdf,rec,'source_corrected_tuned'); rec.flush()
    print('START source_corrected_fixed',flush=True); mod.run_fixed_cohort(newdf,OUT,'source_corrected_fixed',recorder=rec); rec.flush()
    mod.base.require(mod.base.sha256(CORRECTIONS)==design['correction_csv_sha256'],'Correction list changed during run; do not silently mix versions')
    mod.base.require(mod.base.sha256(FACTS)==FACT_HASH and mod.base.sha256(ROOT/'datasets/model_cohort.parquet')==mod.EXPECTED_HASH,'Frozen inputs changed')
    outputs={str(p.relative_to(OUT)):{'sha256':mod.base.sha256(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}
    mod.base.write_json(OUT/'manifest.json',{'status':'complete','design_sha256':mod.base.sha256(OUT/'design.json'),'input_audit':audit,
                      'correction_csv_sha256':design['correction_csv_sha256'],'metric_rows':len(rec.metrics),'artifacts':len(rec.fits),'outputs':outputs})
    print(json.dumps({'complete':True,'audit':audit,'metrics':len(rec.metrics)},default=str),flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser(); parser.add_argument('--version',type=int,choices=[1,2],default=1); args=parser.parse_args()
    VERSION=args.version
    if VERSION==2:
        SUFFIX='_v2'; OUT=REV/'results/corrected_models_v2'
    run()

"""Frozen post hoc development controls, all old project files read-only.

python development_controls.py --plan | --run | --audit
Two CPU threads. No network, new raw data, manuscript edits or packaging.
"""
from __future__ import annotations
import os
for k in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:
    os.environ[k]='2'
import sys
sys.dont_write_bytecode=True
from pathlib import Path
import argparse,hashlib,importlib.util,json,time,shutil
from datetime import datetime,timezone
import numpy as np
import pandas as pd
import joblib
from sklearn.metrics import average_precision_score,roc_auc_score

ROUND=Path(__file__).resolve().parents[1]; ROOT=ROUND.parent
OLD=ROOT/'revision_20260922'; OUT=ROUND/'results/development_controls'
spec=importlib.util.spec_from_file_location('round2_readonly_revision_models',OLD/'scripts/revision_models.py')
rm=importlib.util.module_from_spec(spec);spec.loader.exec_module(rm)
b=rm.base
SEEDS=[20260921,20260922,20260923,20260924,20260925]
MATCH_SEEDS=list(range(2026092201,2026092221))
GROUPS=['positive_unchanged','changed_negative','other_unchanged_negative']
STAGES=['tuning_train','validation','refit']
SOURCE_USES=[]

def jwrite(path,obj):b.write_json(path,obj)
def load():
    assert shutil.disk_usage(ROUND).free>10*1024**3
    df,binding=rm.load_base()
    return df,binding

def group_indices(df):
    changed=np.any(~np.isclose(df[['A_'+f for f in b.FEATURES]].to_numpy(),
                              df[['B_'+f for f in b.FEATURES]].to_numpy(),rtol=0,atol=0,equal_nan=True),axis=1)
    transition=df.form.eq('10-KT').to_numpy(); y=df.registry_event_365.to_numpy()
    groups={'positive_unchanged':np.flatnonzero(transition&(y==1)&~changed),
            'changed_negative':np.flatnonzero(transition&(y==0)&changed),
            'other_unchanged_negative':np.flatnonzero(transition&(y==0)&~changed)}
    assert [len(groups[g]) for g in GROUPS]==[1,2,9]
    assert len(set(np.concatenate(list(groups.values()))))==12
    return groups

def stage_signature(df,split):
    a=pd.DataFrame(index=df.index)
    a['origin_year']=df.decision_date.dt.year
    a['label']=df.registry_event_365
    for stage in STAGES:a[stage]=a.index.isin(split['indices'][stage])
    return a

def matching_plan(df):
    """Match only actually eligible final-development transition records per block.
    No score, feature values, or model output enters candidate selection.
    """
    groups=group_indices(df); records=[]; runs=[]; rows=[]
    for split in b.make_splits(df):
        block=split['block']; sig=stage_signature(df,split)
        refit=set(split['indices']['refit'])
        for group,ids in groups.items():
            active=[int(i) for i in ids if i in refit]
            for i in ids:
                rows.append({'group':group,'block':block,'row_id':df.at[i,'row_id'],
                             **sig.loc[i].to_dict(),'active_final_development':int(i) in refit})
            for repeat,seed in enumerate(MATCH_SEEDS):
                rng=np.random.default_rng(seed+1000*GROUPS.index(group)+100000*int(block[:4]))
                chosen=[]; failed=[]; local=[]
                for target in sorted(active,key=lambda i:df.at[i,'row_id']):
                    eligible=df.form.ne('10-KT').to_numpy(copy=True)
                    for key in sig.columns:eligible &= sig[key].eq(sig.at[target,key]).to_numpy()
                    pool=np.flatnonzero(eligible & ~df.index.isin(chosen))
                    pool=sorted(pool,key=lambda i:df.at[i,'row_id'])
                    selected=int(rng.choice(pool)) if pool else None
                    if selected is None:failed.append(df.at[target,'row_id'])
                    else:chosen.append(selected)
                    local.append({'group':group,'block':block,'repeat':repeat,'seed':seed,
                                  'target_row_id':df.at[target,'row_id'],'selected_row_id':None if selected is None else df.at[selected,'row_id'],
                                  'candidate_pool_n':len(pool),**sig.loc[target].to_dict(),
                                  'target_sample_weight':df.at[target,'sample_weight'],
                                  'selected_sample_weight':None if selected is None else df.at[selected,'sample_weight']})
                status='inactive_no_development_record' if not active else ('insufficient_exact_pool' if failed else 'ready')
                records.extend(local)
                runs.append({'group':group,'block':block,'repeat':repeat,'seed':seed,'status':status,
                             'n_target':len(active),'target_row_ids':df.loc[active,'row_id'].tolist(),
                             'selected_row_ids':df.loc[chosen,'row_id'].tolist(),'unmatched_target_row_ids':failed})
    return records,runs,rows

def ensure_plan(df,binding):
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/'design.json'
    if path.exists():
        plan=json.loads(path.read_text(encoding='utf-8'))
        assert plan['script_sha256']==b.sha256(__file__),'Script changed after freeze; amend explicitly'
        assert plan['input_binding']==binding
        return plan
    records,runs,rows=matching_plan(df)
    pd.DataFrame(records).to_csv(OUT/'matched_selected_records.csv',index=False)
    pd.DataFrame(rows).to_csv(OUT/'transition_group_stage_membership.csv',index=False)
    jwrite(OUT/'matched_deletion_plan.json',runs)
    plan={'created_utc':datetime.now(timezone.utc).isoformat(),
      'route':'SCI measurement/validation protocol; not a causal or deployment claim',
      'analysis_status':'post_hoc_second_revision; previous held-out scores already known; controls fixed before their execution',
      'script_sha256':b.sha256(__file__),'readonly_revision_script_sha256':b.sha256(OLD/'scripts/revision_models.py'),
      'input_binding':binding,'threads':2,'model_seed':rm.SEED,'randomness_seeds':SEEDS,'matching_seeds':MATCH_SEEDS,
      'fixed_parameters':{'LR':rm.FIXED['LR'],'LGBM':rm.FIXED['LGBM'],'RF':rm.FIXED['RF']},
      'LGBM_grid':b.model_grid('LGBM'),
      'identical_input':'Set every B financial feature equal to A; independently run original four-candidate tuning and final refit for LR/LGBM in both arms, same seed/order/weights; score all four cells. Compare candidate AP, selection, weighted preprocessing and paired predictions within 1e-12. Implementation check, not empirical novelty.',
      'algorithm_seeds':'A inputs only, fixed LGBM/RF, five seeds, unchanged preprocessing/splits/order. No new bagging or feature-sampling randomness is enabled. Report whether LGBM seed has any active stochastic source.',
      'transition_groups':{'positive_unchanged':1,'changed_negative':2,'other_unchanged_negative':9},
      'deletion':'Drop only group members actually in each block final mature refit. Fixed common LR/LGBM parameters. All original test observations and design evaluation weights retained. Inactive groups reuse full models and are labeled zero intervention.',
      'ordinary_matching':'Ordinary non-10-KT records matched exactly on decision/origin calendar year, event label and original tuning_train/validation/refit membership tuple within block. Group-wise without replacement; repetitions may overlap. Twenty fixed RNG seeds; candidates never depend on scores or feature values. Sampling stratum is NOT a matching criterion; record target and selected weights for transparency. No approximate matching fallback.',
      'CPI_domains':['full_train_full_test','full_train_size_test','size_train_size_test'],
      'CPI_rule':'Previously frozen original-A CPI origin-size indicator. Same test subset in the latter two. Reuse archived fits after checksum/training-row/input checks; no new fitting necessary.',
      'absolute_spline_RF':'Reuse prior fixed spline/RF artifacts and publish full AA/BB absolute AP/Brier as well as difference.',
      'metrics':'Original design-weighted AP primary; Brier/ROC/tie-aware weighted-capacity recall and weighted/unweighted prevalence secondary. All four cells retained.',
      'comparison':'Deletion minus full baseline changes and descriptive matched-deletion distributions; no significance or causal claims and no test-based parameter choice.',
      'time_rule':'Original chronological blocks and decision+365+90 day maturity; no earlier-year label borrowing.',
      'failure_policy':'Record unsupported exact matches or failed fits; do not silently change candidates, seeds, domains, or test sets.',
      'resources':'CPU two threads; about 700 small tabular fits including tuning; expected under 20 minutes and under 3 GiB output; zero network/API costs.',
      'matching_plan_sha256':b.sha256(OUT/'matched_deletion_plan.json'),
      'matching_selected_records_sha256':b.sha256(OUT/'matched_selected_records.csv'),
      'matching_status_counts':pd.Series([r['status'] for r in runs]).value_counts().to_dict()}
    jwrite(path,plan)
    (OUT/'design.md').write_text('# Frozen second-revision development controls\n\nAll controls are post hoc relative to the previous study. This plan and exact matched row lists were written before the new control fits.\n\n1. Full B=A pipeline check: independent original-grid tuning, both learners, all blocks and all four cells.\n2. Five predetermined A-only seeds for fixed LightGBM and random forest; do not introduce new randomness.\n3. Three disjoint transition groups (1 positive, 2 changed negatives, 9 other unchanged negatives), remove mature development members only; common fixed parameters and full original test. Twenty exact ordinary matched deletions per active group/block.\n4. All four original LightGBM candidates as common fixed final-fit configurations.\n5. Full/full, full/CPI-size, CPI-size/CPI-size comparisons and absolute spline/RF results from bound archived models.\n\nMatching fixes origin year, label and three original development-stage memberships. Repeated samples may overlap across repetitions, never within a group/repetition. No approximate fallback. The selected records and seeds are frozen in CSV/JSON.\n\nWeighted AP and Brier are reported as absolute levels and paired changes; matched variability is descriptive, not an inferential null distribution. No test-based selection is made. Input identity, maturity, fitting inputs and numerical metrics will be audited.\n',encoding='utf-8')
    return plan

def archived(experiment,block,version,learner,folder='models'):
    directory=OLD/'results'/folder
    records=json.loads((directory/'fit_preprocessing_audit.json').read_text(encoding='utf-8'))
    entry=[r for r in records if r['experiment']==experiment and r['block']==block and r['version']==version and r['model']==learner]
    assert len(entry)==1,(experiment,block,version,learner)
    entry=entry[0]; path=directory/'artifacts'/Path(entry['artifact']).name
    assert b.sha256(path)==entry['sha256']
    SOURCE_USES.append({'path':str(path),'sha256':entry['sha256']})
    return joblib.load(path)

def validate_train(bundle,df,idx):
    assert bundle['train_row_ids']==df.loc[idx,'row_id'].tolist()
    x=rm.matrix(df,idx,bundle['train_version'])
    digest=hashlib.sha256(pd.util.hash_pandas_object(df.loc[idx,['row_id','registry_event_365','sample_weight']],index=False).values.tobytes()+x.tobytes()).hexdigest()
    assert digest==bundle['train_rows_features_labels_weights_sha256']

def fixed_block(df,rec,split,experiment,remove=(),params=None,learners=('LR','LGBM'),test_ids=None,force_fit=False):
    block=split['block']; train=split['indices']['refit']; test=split['indices']['test'] if test_ids is None else np.asarray(test_ids)
    train=train[~np.isin(train,list(remove))]
    rec.split(df,train,experiment,block,'refit',split['test_start']);rec.split(df,test,experiment,block,'test')
    for learner in learners:
        parameters=rm.FIXED[learner] if params is None else params
        for version in ['A','B']:
            reuse=not len(remove) and parameters==rm.FIXED[learner] and not force_fit
            bundle=archived('fixed_full',block,version,learner) if reuse else rm.fit_pipeline(df,train,version,learner,parameters)
            validate_train(bundle,df,train)
            rec.save_fit(bundle,experiment,block,version,learner,stage='reused_archived' if reuse else 'final')
            for score_version in ['A','B']:rec.score(bundle,df,test,experiment,block,version,score_version,learner)

def identity_control(df,rec):
    same=df.copy()
    for f in b.FEATURES:same['B_'+f]=same['A_'+f]
    rm.run_tuned(same,rec,'identical_input_tuned')
    checks=[]
    for block in [s['block'] for s in b.make_splits(same)]:
        for learner in ['LR','LGBM']:
            parts=[r for r in rec.fits if r['experiment']=='identical_input_tuned' and r['block']==block and r['model']==learner]
            assert len(parts)==2
            a,bb=sorted(parts,key=lambda r:r['version'])
            assert a['parameters']==bb['parameters'] and a['preprocessing']==bb['preprocessing']
            assert a['training_input_digest']==bb['training_input_digest']
            logs=[r for r in rec.selection if r.get('experiment')=='identical_input_tuned' and r.get('block')==block and r.get('model')==learner]
            chosen=[r for r in logs if r.get('stage')=='selection']; assert len(chosen)==2
            assert chosen[0]['chosen']==chosen[1]['chosen']
            candidates=[r for r in logs if 'candidate' in r]
            for candidate in range(4):
                pair=[r for r in candidates if r['candidate']==candidate]
                assert len(pair)==2 and pair[0]['metrics']==pair[1]['metrics'] and pair[0]['preprocessing']==pair[1]['preprocessing']
            pred=pd.concat([p for p in rec.predictions if p.experiment.iloc[0]=='identical_input_tuned' and p.block.iloc[0]==block and p.model.iloc[0]==learner])
            wide=pred.pivot(index='row_id',columns=['train_version','score_version'],values='pred')
            error=float(np.max(np.abs(wide.to_numpy()-wide.iloc[:,[0]].to_numpy())))
            assert error<=1e-12
            checks.append({'block':block,'model':learner,'preprocessing_equal':True,'all_four_candidate_metrics_equal':True,
                           'selection_equal':True,'four_cell_max_abs_prediction_difference':error})
    jwrite(OUT/'identical_input_audit.json',{'status':'PASS','checks':checks})

def seed_controls(df,rec):
    old_seed,old_base_seed=rm.SEED,b.SEED
    settings=[]
    try:
        for seed in SEEDS:
            rm.SEED=b.SEED=seed
            for split in b.make_splits(df):
                experiment=f'algorithm_seed_{seed}'; train=split['indices']['refit']; test=split['indices']['test'];block=split['block']
                rec.split(df,train,experiment,block,'refit',split['test_start']);rec.split(df,test,experiment,block,'test')
                for learner in ['LGBM','RF']:
                    bundle=rm.fit_pipeline(df,train,'A',learner)
                    bundle['control_seed']=seed
                    rec.save_fit(bundle,experiment,block,'A',learner)
                    rec.score(bundle,df,test,experiment,block,'A','A',learner)
                    settings.append({'seed':seed,'block':block,'model':learner,'get_params':bundle['model'].get_params()})
    finally:rm.SEED,b.SEED=old_seed,old_base_seed
    jwrite(OUT/'algorithm_seed_settings.json',settings)

def reuse_domain_and_spline(df,rec):
    indicator=pd.read_parquet(OLD/'datasets/cpi_origin_domain.parquet')
    assert indicator.row_id.tolist()==df.row_id.tolist()
    size=indicator.included.to_numpy(dtype=bool)
    for split in b.make_splits(df):
        block=split['block'];alltest=split['indices']['test'];smalltest=alltest[size[alltest]]
        fixed_block(df,rec,split,'full_train_full_test')
        fixed_block(df,rec,split,'full_train_size_test',test_ids=smalltest)
        smalltrain=split['indices']['refit'][size[split['indices']['refit']]]
        rec.split(df,smalltrain,'size_train_size_test',block,'refit',split['test_start']);rec.split(df,smalltest,'size_train_size_test',block,'test')
        for learner in ['LR','LGBM']:
            for version in ['A','B']:
                bundle=archived('cpi1980_size_fixed',block,version,learner,'cpi_domain')
                validate_train(bundle,df,smalltrain)
                rec.save_fit(bundle,'size_train_size_test',block,version,learner,stage='reused_archived')
                for sv in ['A','B']:rec.score(bundle,df,smalltest,'size_train_size_test',block,version,sv,learner)
        for learner in ['SPLINE_LR','RF']:
            for version in ['A','B']:
                bundle=archived('fixed_spline_rf',block,version,learner)
                validate_train(bundle,df,split['indices']['refit'])
                rec.save_fit(bundle,'absolute_spline_rf',block,version,learner,stage='reused_archived')
                for sv in ['A','B']:rec.score(bundle,df,alltest,'absolute_spline_rf',block,version,sv,learner)

def table_outputs(rec):
    metrics=pd.DataFrame(rec.metrics); dif=rm.four_cell_differences(metrics)
    dif.to_csv(OUT/'four_cell_differences.csv',index=False)
    ap=dif[dif.metric.eq('average_precision')]
    ap.to_csv(OUT/'ap_four_cells.csv',index=False)
    metrics[metrics.train_version.eq(metrics.score_version)].to_csv(OUT/'absolute_diagonal_metrics.csv',index=False)
    metrics[metrics.experiment.isin(['full_train_full_test','full_train_size_test','size_train_size_test'])].to_csv(OUT/'CPI_domain_metrics.csv',index=False)
    baseline=ap[ap.experiment.eq('full_train_full_test')].set_index(['block','model'])
    deletions=ap[ap.experiment.str.startswith(('transition_delete_','ordinary_matched_'))].copy()
    for name in ['AA','BB','total_refit_difference']:
        deletions[name+'_minus_full']=[r[name]-baseline.loc[(r.block,r.model),name] for _,r in deletions.iterrows()]
    deletions.to_csv(OUT/'deletion_AP_changes.csv',index=False)
    comparisons=[]
    for group in GROUPS:
        for (block,model),part in deletions[deletions.experiment.eq('transition_delete_'+group)].groupby(['block','model']):
            target=part.iloc[0]; ordinary=deletions[deletions.experiment.str.startswith('ordinary_matched_'+group+'_')&deletions.block.eq(block)&deletions.model.eq(model)]
            row={'group':group,'block':block,'model':model,'ordinary_repetitions':len(ordinary),
                 'transition_delta_AP':target.total_refit_difference,'transition_delta_change':target.total_refit_difference_minus_full,
                 'transition_AA':target.AA,'transition_BB':target.BB}
            if len(ordinary):
                x=ordinary.total_refit_difference_minus_full.to_numpy()
                row.update(ordinary_delta_change_min=float(x.min()),ordinary_delta_change_median=float(np.median(x)),ordinary_delta_change_max=float(x.max()),
                           ordinary_absolute_change_ge_transition_fraction=float(np.mean(abs(x)>=abs(target.total_refit_difference_minus_full)-1e-12)))
            comparisons.append(row)
    pd.DataFrame(comparisons).to_csv(OUT/'matched_deletion_comparison.csv',index=False)
    pred=pd.concat(rec.predictions,ignore_index=True); seedrows=[]
    for (block,model),g in pred[pred.experiment.str.startswith('algorithm_seed_')].groupby(['block','model']):
        wide=g.pivot(index='row_id',columns='experiment',values='pred')
        m=metrics[metrics.experiment.str.startswith('algorithm_seed_')&metrics.block.eq(block)&metrics.model.eq(model)]
        seedrows.append({'block':block,'model':model,'seeds':len(m),'AP_min':m.average_precision.min(),'AP_max':m.average_precision.max(),
                         'AP_range':m.average_precision.max()-m.average_precision.min(),'Brier_min':m.brier.min(),'Brier_max':m.brier.max(),
                         'max_prediction_range':float((wide.max(axis=1)-wide.min(axis=1)).max())})
    pd.DataFrame(seedrows).to_csv(OUT/'algorithm_seed_summary.csv',index=False)

def audit():
    df,_=load(); metrics=pd.read_csv(OUT/'metrics.csv'); pred=pd.read_parquet(OUT/'predictions.parquet')
    maxerror=0.; checks=0; keys=['experiment','block','model','train_version','score_version']
    for group,g in pred.groupby(keys,sort=False):
        stored=metrics
        for key,value in zip(keys,group):stored=stored[stored[key].eq(value)]
        assert len(stored)==1;stored=stored.iloc[0]
        y=g.label.to_numpy();p=g.pred.to_numpy();w=g.sample_weight.to_numpy()
        values={'average_precision':average_precision_score(y,p,sample_weight=w),'roc_auc':roc_auc_score(y,p,sample_weight=w),'brier':np.average((y-p)**2,weights=w)}
        # Independent tied-score capacity computation: all records at a boundary receive one common fraction.
        selected=np.zeros(len(g));remaining=.05*w.sum()
        for value in np.sort(np.unique(p))[::-1]:
            at=np.flatnonzero(p==value);mass=w[at].sum();fraction=min(1.,max(0.,remaining/mass))
            selected[at]=fraction;remaining-=fraction*mass
        values['retrospective_recall_at_5percent']=float(np.dot(selected*w,y)/np.dot(w,y))
        assert np.allclose(selected,g.retrospective_selection_fraction_at_5percent,rtol=0,atol=1e-12)
        for name,value in values.items():
            error=abs(value-stored[name]);maxerror=max(maxerror,error);assert error<1e-12,(group,name,error)
        checks+=1
    idmap=pd.Series(df.index,index=df.row_id); split_records=json.loads((OUT/'split_audit.json').read_text(encoding='utf-8'))
    for s in split_records:
        if s.get('fit_or_selection_cutoff') is not None:
            assert df.loc[idmap.loc[s['row_ids']].to_numpy(),'mature_date'].le(pd.Timestamp(s['fit_or_selection_cutoff'])).all()
        if s['stage']=='test' and s['experiment'].startswith(('transition_delete_','ordinary_matched_','identical_input_')):
            expected=next(x for x in b.make_splits(df) if x['block']==s['block'])['indices']['test']
            assert s['row_ids']==df.loc[expected,'row_id'].tolist()
    fits=json.loads((OUT/'fit_preprocessing_audit.json').read_text(encoding='utf-8'))
    maximum_prediction_error=0.
    same=df.copy()
    for f in b.FEATURES:same['B_'+f]=same['A_'+f]
    for entry in fits:
        path=OUT/'artifacts'/Path(entry['artifact']).name;assert b.sha256(path)==entry['sha256']
        bundle=joblib.load(path);current=same if entry['experiment']=='identical_input_tuned' else df
        train=idmap.loc[bundle['train_row_ids']].to_numpy();validate_train(bundle,current,train)
        g=pred[pred.experiment.eq(entry['experiment'])&pred.block.eq(entry['block'])&pred.model.eq(entry['model'])&pred.train_version.eq(entry['version'])]
        for sv,part in g.groupby('score_version'):
            scores=rm.score_pipeline(bundle,current,idmap.loc[part.row_id].to_numpy(),sv)
            error=float(np.abs(scores-part.pred.to_numpy()).max());maximum_prediction_error=max(maximum_prediction_error,error)
            assert error<1e-12
    matched=pd.read_csv(OUT/'matched_selected_records.csv')
    for (group,block,repeat),part in matched.groupby(['group','block','repeat']):
        if part.selected_row_id.isna().any():continue
        assert part.selected_row_id.is_unique
        split=next(s for s in b.make_splits(df) if s['block']==block);sig=stage_signature(df,split)
        for row in part.itertuples():
            target=int(idmap.loc[row.target_row_id]);selected=int(idmap.loc[row.selected_row_id])
            assert sig.loc[target].equals(sig.loc[selected]) and df.at[selected,'form']!='10-KT'
    report={'status':'PASS','independently_recomputed_metric_cells':checks,'maximum_metric_difference':maxerror,
            'saved_artifacts_reconstructed':len(fits),'maximum_prediction_difference':maximum_prediction_error,
            'maturity_and_complete_test_guards':'PASS','exact_matched_selected_records':'PASS',
            'input_sha256':b.sha256(ROOT/'datasets/model_cohort.parquet'),'no_changes_to_old_files':True,
            'warnings':[{'experiment':r['experiment'],'block':r['block'],'model':r['model'],'version':r['version'],'warnings':r['warnings']} for r in fits if r.get('warnings') or not r.get('converged',True)]}
    assert report['input_sha256']==rm.EXPECTED_HASH
    jwrite(OUT/'numerical_audit.json',report);print(json.dumps(report),flush=True)
    return report

def run():
    df,binding=load();plan=ensure_plan(df,binding)
    assert not (OUT/'run_manifest.json').exists() and not (OUT/'artifacts').exists(),'Inspect partial run; never overwrite'
    rec=rm.Recorder(OUT);started=datetime.now(timezone.utc).isoformat()
    operations=[('identical_input_tuned',lambda:identity_control(df,rec)),('algorithm_seeds',lambda:seed_controls(df,rec)),
                ('archived_domains_and_absolute_baselines',lambda:reuse_domain_and_spline(df,rec))]
    for name,fn in operations:
        print('START '+name,flush=True);start=time.perf_counter();fn();rec.flush();print('COMPLETE '+name+' '+str(time.perf_counter()-start),flush=True)
    for candidate,params in enumerate(b.model_grid('LGBM')):
        for split in b.make_splits(df):fixed_block(df,rec,split,f'grid_fixed_LGBM_{candidate}',params=params,learners=('LGBM',))
    rec.flush();print('COMPLETE four fixed LGBM candidates',flush=True)
    groups=group_indices(df)
    for split in b.make_splits(df):
        for group,ids in groups.items():
            active=np.intersect1d(ids,split['indices']['refit'])
            fixed_block(df,rec,split,'transition_delete_'+group,remove=active)
    rec.flush();print('COMPLETE transition groups',flush=True)
    matches=json.loads((OUT/'matched_deletion_plan.json').read_text(encoding='utf-8'))
    idmap=pd.Series(df.index,index=df.row_id)
    for i,match in enumerate(matches):
        if match['status']!='ready':continue
        split=next(s for s in b.make_splits(df) if s['block']==match['block'])
        ids=idmap.loc[match['selected_row_ids']].to_numpy()
        fixed_block(df,rec,split,f"ordinary_matched_{match['group']}_{match['repeat']:02d}",remove=ids)
        if (i+1)%10==0:print('MATCHED PLAN '+str(i+1)+'/'+str(len(matches)),flush=True)
    rec.flush();table_outputs(rec)
    jwrite(OUT/'archived_source_artifacts.json',SOURCE_USES)
    audit_report=audit()
    outputs={str(p.relative_to(OUT)):{'sha256':b.sha256(p),'bytes':p.stat().st_size} for p in OUT.rglob('*') if p.is_file()}
    jwrite(OUT/'run_manifest.json',{'status':'COMPLETE','started_utc':started,'completed_utc':datetime.now(timezone.utc).isoformat(),
       'design_sha256':b.sha256(OUT/'design.json'),'script_sha256':b.sha256(__file__),'input_binding':binding,
       'fits_or_reused_artifacts':len(rec.fits),'metric_cells':len(rec.metrics),'predictions':sum(len(p) for p in rec.predictions),
       'threads':2,'numerical_audit':audit_report,'outputs':outputs})
    print('ALL COMPLETE',flush=True)

if __name__=='__main__':
    parser=argparse.ArgumentParser();g=parser.add_mutually_exclusive_group(required=True)
    g.add_argument('--plan',action='store_true');g.add_argument('--run',action='store_true');g.add_argument('--audit',action='store_true')
    args=parser.parse_args()
    if args.plan:
        df,binding=load();p=ensure_plan(df,binding);print(json.dumps({'plan':str(OUT/'design.json'),'matching':p['matching_status_counts']}),flush=True)
    elif args.audit:audit()
    else:run()

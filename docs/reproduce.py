"""Offline round-two recalculation from frozen predictions; no training or network."""
from pathlib import Path
import os,sys
for key in ['OMP_NUM_THREADS','OPENBLAS_NUM_THREADS','MKL_NUM_THREADS']:os.environ[key]='2'
sys.dont_write_bytecode=True
import argparse,ast,hashlib,importlib.util,json,shutil
import numpy as np,pandas as pd
from sklearn.metrics import average_precision_score,roc_auc_score

def sha(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for b in iter(lambda:f.read(1048576),b''):h.update(b)
    return h.hexdigest()
def module(name,path):
    spec=importlib.util.spec_from_file_location(name,path);obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def write(path,obj):path.write_text(json.dumps(obj,ensure_ascii=False,indent=2),encoding='utf-8')

def recall(y,p,w):
    ix=np.argsort(-p,kind='stable');v=p[ix];starts=np.r_[0,np.flatnonzero(v[1:]!=v[:-1])+1]
    mass=np.add.reduceat(w[ix],starts);positive=np.add.reduceat(w[ix]*y[ix],starts)
    before=np.r_[0,np.cumsum(mass)[:-1]];frac=np.clip((.05*w.sum()-before)/mass,0,1)
    return float(np.dot(frac,positive)/np.dot(w,y))

def recalculate_metrics(directory,out,name):
    predictions=pd.read_parquet(directory/'predictions.parquet');stored=pd.read_csv(directory/'metrics.csv')
    keys=['experiment','block','model','train_version','score_version'];reference=stored.set_index(keys)
    assert reference.index.is_unique
    rows=[];maxerror=0.
    for key,g in predictions.groupby(keys,sort=False):
        y=g['label'].to_numpy();p=g['pred'].to_numpy();w=g.sample_weight.to_numpy()
        values={'average_precision':average_precision_score(y,p,sample_weight=w),'roc_auc':roc_auc_score(y,p,sample_weight=w),
                'brier':float(np.average((y-p)**2,weights=w)),'retrospective_recall_at_5percent':recall(y,p,w)}
        prior=reference.loc[key]
        for metric,value in values.items():
            error=abs(value-prior[metric]);assert error<1e-12,(name,key,metric,error);maxerror=max(maxerror,error)
        rows.append(dict(zip(keys,key),**values,n=len(g),positive_windows=int(y.sum()),weighted_n=float(w.sum()),weighted_prevalence=float(np.dot(y,w)/w.sum())))
    result=pd.DataFrame(rows);result.to_csv(out/(name+'_metrics_recalculated.csv'),index=False)
    dif=[]
    for key,g in result.groupby(keys[:3],sort=False):
        cells={(r.train_version,r.score_version):r for _,r in g.iterrows()}
        if all(z in cells for z in [('A','A'),('A','B'),('B','A'),('B','B')]):
            for metric in ['average_precision','brier','roc_auc','retrospective_recall_at_5percent']:
                aa,ab,ba,bb=[cells[z][metric] for z in [('A','A'),('A','B'),('B','A'),('B','B')]]
                dif.append(dict(zip(keys[:3],key),metric=metric,AA=aa,AB=ab,BA=ba,BB=bb,input_change=ab-aa,fit_change=ba-aa,interaction=bb-ba-ab+aa,total=bb-aa))
    pd.DataFrame(dif).to_csv(out/(name+'_four_cells_recalculated.csv'),index=False)
    return {'group':name,'metric_rows':len(rows),'individual_metrics':4*len(rows),'maximum_difference':maxerror}

def compare_numeric(new,old,keys):
    a=pd.read_parquet(new) if new.suffix=='.parquet' else pd.read_csv(new)
    b=pd.read_parquet(old) if old.suffix=='.parquet' else pd.read_csv(old)
    a=a.set_index(keys).sort_index();b=b.set_index(keys).sort_index();assert a.index.equals(b.index)
    cols=[k for k in a.select_dtypes(include='number').columns if k in b]
    err=0.
    for c in cols:
        assert np.allclose(a[c],b[c],rtol=0,atol=1e-12,equal_nan=True),(new.name,c)
        values=np.abs(a[c]-b[c]);err=max(err,float(values.max()) if values.notna().any() else 0.)
    return {'file':new.name,'rows':len(a),'numeric_columns':len(cols),'maximum_difference':err}

def identity_checks(root,rev):
    source=root/'datasets/model_cohort.parquet';assert sha(source)=='724122d3ca7a0a123de244112aa604d6da7a008497cc6ce526f8f07327916e21'
    main=pd.read_parquet(source);main['row_id']=main.cik+'|'+main.accession
    main['decision_date']=pd.to_datetime(main.decision_date);main['mature_date']=main.decision_date+pd.Timedelta(days=455)
    features=['log_assets','liabilities_to_assets','equity_to_assets','cash_to_assets','net_income_to_assets','revenue_to_assets','operating_income_to_assets','operating_cash_to_assets','retained_earnings_to_assets','working_capital_to_assets']
    stable=['row_id','cik','accession','cluster_id','registry_event_365','sample_weight','decision_date','mature_date']
    def same_column(a,z,key):
        if key in ['decision_date','mature_date']:
            return np.array_equal(pd.to_datetime(a).to_numpy(dtype='datetime64[ns]'),pd.to_datetime(z).to_numpy(dtype='datetime64[ns]'))
        return np.array_equal(a.to_numpy(),z.to_numpy())
    checks=[];trace=pd.read_parquet(rev/'results/fit_date/fit_date_lineage.parquet')
    for block in ['2016_2017','2018_2019','2020_2021']:
        frame=pd.read_parquet(rev/f'datasets/fit_date_{block}.parquet');cutoff=pd.Timestamp(int(block[:4]),1,1)
        for k in stable:assert same_column(frame[k],main[k],k),(block,k)
        assert np.allclose(frame[['A_'+f for f in features]],main[['A_'+f for f in features]],rtol=0,atol=0,equal_nan=True)
        assert np.array_equal(frame[['B_'+f for f in features]].isna(),main[['A_'+f for f in features]].isna())
        train=main.mature_date.le(cutoff); test=main.decision_date.dt.year.between(int(block[:4]),int(block[-4:]))
        t=trace[trace.block.eq(block)]
        assert set(t.row_id)==set(main.loc[train,'row_id']) and t.row_id.is_unique
        assert pd.to_datetime(t.selected_filed).lt(cutoff).all()
        assert np.allclose(frame.loc[test,['B_'+f for f in features]],main.loc[test,['A_'+f for f in features]],rtol=0,atol=0,equal_nan=True)
        checks.append({'block':block,'fit_date_cutoff_and_fixed_A_test':'PASS','training_rows':int(train.sum())})
    scaled=pd.read_parquet(rev/'datasets/source_verified_corrected_scale_only.parquet')
    for k in stable:
        if k in scaled:assert same_column(scaled[k],main[k],k),k
    changed={}
    for arm in ['A','B']:
        x=main[[arm+'_'+f for f in features]].to_numpy();z=scaled[[arm+'_'+f for f in features]].to_numpy()
        assert np.array_equal(np.isnan(x),np.isnan(z));different=~np.isclose(x,z,rtol=0,atol=0,equal_nan=True)
        assert different.sum()==1 and not different[:,1:].any()
        assert np.allclose(z[:,0][different[:,0]]-x[:,0][different[:,0]],np.log(1000),rtol=0,atol=1e-12)
        changed[arm]=int(different.sum())
    contexts=pd.read_csv(rev/'results/scale_only/verified_corrections_snapshot.csv');assert len(contexts)==22
    checks.append({'scale_only_contexts':22,'A_B_changed_features':changed,'ratios_unchanged':'PASS'})
    return checks

def redirected_script(script,paths):
    """Run the frozen display code with only its output-path assignments replaced.

    Input roots still resolve from the script's real __file__. No model, numerical
    formula, source data, or archived script is changed by this adapter.
    """
    tree=ast.parse(script.read_text(encoding='utf-8'),filename=str(script))
    removed=[];body=[]
    for node in tree.body:
        names=[t.id for t in node.targets if isinstance(t,ast.Name)] if isinstance(node,ast.Assign) else []
        if any(k in paths for k in names):
            assert len(names)==1 and len(node.targets)==1,(script.name,names)
            removed.extend(names)
        else:body.append(node)
    assert set(removed)==set(paths),(script.name,removed,paths)
    tree.body=body
    for name,path in paths.items():
        (path.parent if name=='dest' else path).mkdir(parents=True,exist_ok=True)
    env={'__name__':'__main__','__file__':str(script),**paths}
    exec(compile(ast.fix_missing_locations(tree),str(script),'exec'),env)
    return {'script':script.name,'frozen_script_sha256':sha(script),'redirected_output_names':removed}

def rebuild_presentation(rev,out):
    displays=rev/'scripts/build_main_displays.py';assembler=rev/'scripts/assemble_main.py'
    if not displays.exists() or not assembler.exists():
        return {'status':'scripts_not_present_in_this_draft'}
    man=out/'manuscript';fig=out/'figures';man.mkdir(parents=True,exist_ok=True)
    shutil.copy2(rev/'manuscript/main_template.md',man/'main_template.md')
    runs=[redirected_script(displays,{'OUT':man,'FIG':fig}),redirected_script(assembler,{'M':man})]
    summary=json.loads((man/'content_summary.json').read_text(encoding='utf-8'))
    assert (man/'manuscript.md').read_bytes()==(rev/'manuscript/manuscript.md').read_bytes()
    assert (man/'generated_tables.json').read_bytes()==(rev/'manuscript/generated_tables.json').read_bytes()
    assert (man/'references.bib').read_bytes()==(rev/'manuscript/references.bib').read_bytes()
    figure_files=sorted(p.name for p in fig.iterdir() if p.suffix in ['.png','.pdf','.svg'])
    assert len(figure_files)==3*summary['figures'],figure_files
    supplement=None
    script=rev/'scripts/build_supplement.py'
    if script.exists() and (rev/'manuscript/supplement.md').exists():
        runs.append(redirected_script(script,{'OUT':out/'supplement_tables','dest':man/'supplement.md'}))
        assert (man/'supplement.md').read_bytes()==(rev/'manuscript/supplement.md').read_bytes()
        supplement=json.loads((out/'supplement_tables/build_manifest.json').read_text(encoding='utf-8'))
        supplement={'table_count':supplement['table_count'],'supplement_sha256':sha(man/'supplement.md'),
                    'supplement_byte_equal':True,'training_performed':False}
    return {'status':'PASS','runs':runs,'content_summary':summary,'figure_files':figure_files,
            'manuscript_tables_bibliography_byte_equal':True,'supplement_rebuild':supplement,'word_rebuild':'not_requested'}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--project',type=Path,default=Path(__file__).resolve().parents[2]);parser.add_argument('--output-dir',type=Path)
    parser.add_argument('--skip-manuscript',action='store_true');args=parser.parse_args()
    root=args.project.resolve();rev=root/'revision_20260922_round2';old=root/'revision_20260922'
    out=args.output_dir.resolve() if args.output_dir else rev/'reproduced';out.mkdir(parents=True,exist_ok=True)
    report={'status':'RUNNING','training':'NOT_PERFORMED','network_requests':0,'mode':'offline_prediction_and_lineage_recalculation'}
    manifestpath=root/'PACKAGE_MANIFEST.json'
    if manifestpath.exists():
        package=json.loads(manifestpath.read_text(encoding='utf-8'))
        for entry in package['files']:assert sha(root/entry['path'])==entry['package_sha256'],entry['path']
        report['package_hashes_checked']=len(package['files'])
    report['identity_checks']=identity_checks(root,rev)
    sys.path.insert(0,str(root/'scripts'));sys.path.insert(0,str(old/'scripts'))
    oldentry=module('round2_previous_portable_entry',old/'reproducibility/reproduce.py')
    oldout=out/'previous_round';oldout.mkdir(exist_ok=True)
    _,_,oldreport=oldentry.verify(root,old,oldout,True)
    report['previous_round_verification']=oldreport
    report['metrics']=[recalculate_metrics(rev/'results/development_controls',out,'development_controls'),
                       recalculate_metrics(rev/'results/fit_date/models',out,'fit_date'),
                       recalculate_metrics(rev/'results/scale_only',out,'scale_only')]
    ed=module('portable_round2_evaluation',rev/'scripts/evaluation_diagnostics.py')
    ed.OUT=out/'evaluation_diagnostics';ed.OUT.mkdir(exist_ok=True)
    report['four_cell_and_conditional_recomputation']=ed.four_cells_and_conditional_check()
    ed.perturbation_modes()
    report['perturbation_comparisons']=[compare_numeric(ed.OUT/'perturbation_modes_all_replicates.parquet',rev/'results/evaluation_diagnostics/perturbation_modes_all_replicates.parquet',['replicate','block','model','mode','metric']),
         compare_numeric(ed.OUT/'perturbation_modes_distribution_summary.csv',rev/'results/evaluation_diagnostics/perturbation_modes_distribution_summary.csv',['block','model','mode','metric','quantity'])]
    report['formal_refitting_draws']=200
    report['new_model_fits']=0
    report['presentation_rebuild']='not_requested'
    if not args.skip_manuscript:report['presentation_rebuild']=rebuild_presentation(rev,out)
    if manifestpath.exists():
        for entry in package['files']:assert sha(root/entry['path'])==entry['package_sha256'],entry['path']
        report['archived_files_unchanged_after_execution']=True
    report['status']='PASS';write(out/'reproduction_report.json',report)
    print(json.dumps({'status':'PASS','output':str(out),'metric_groups':report['metrics'],'formal_refit_draws':200,'new_model_fits':0,'presentation':report['presentation_rebuild']}),flush=True)

if __name__=='__main__':main()

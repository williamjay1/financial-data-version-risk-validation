"""Assemble supplementary tables from frozen results; no fitting or source edits.

Outputs only manuscript/supplement.md and results/supplement_tables/.
Every table has a full-precision CSV/JSON and a source/operation mapping.
"""
from pathlib import Path
import ast
import hashlib
import json
import re
import numpy as np
import pandas as pd

REV = Path(__file__).resolve().parents[1]
ROOT = REV.parent
OLD = ROOT / 'revision_20260922'
OUT = REV / 'results/supplement_tables'
OUT.mkdir(parents=True, exist_ok=True)
ED = REV / 'results/evaluation_diagnostics'
DC = REV / 'results/development_controls'
sources = {}
tables = {}
mapping = []

def register(path):
    path = Path(path)
    key = path.relative_to(ROOT).as_posix()
    sources[key] = hashlib.sha256(path.read_bytes()).hexdigest()
    return key

def csv(path, **kwargs):
    register(path)
    return pd.read_csv(path, **kwargs)

def js(path):
    register(path)
    return json.loads(Path(path).read_text(encoding='utf-8'))

def pq(path):
    register(path)
    return pd.read_parquet(path)

def fmt(x, digits=3, mult=1):
    return '—' if pd.isna(x) else f'{float(x)*mult:.{digits}f}'

def block(x):
    return 'Full cohort' if str(x)=='full_cohort' else str(x).replace('_', '–')

def make_table(key, title, data, display, note, src, operation):
    number = len(tables) + 1
    table_id = f'S{number}'
    data.to_csv(OUT / f'{table_id}_{key}.csv', index=False)
    records=data.astype(object).where(pd.notna(data),None).to_dict('records')
    (OUT / f'{table_id}_{key}.json').write_text(json.dumps(records,indent=2,ensure_ascii=False,allow_nan=False,default=str), encoding='utf-8')
    def clean(v):
        return str(v).replace('|', r'\|').replace('\n',' ')
    cols=list(display.columns)
    lines=['| '+' | '.join(cols)+' |', '| '+' | '.join(['---']*len(cols))+' |']
    lines += ['| '+' | '.join(clean(v) for v in row)+' |' for row in display.itertuples(index=False,name=None)]
    tables[key] = f'Table {table_id}. {title}\n\n'+'\n'.join(lines)+'\n\n'+note
    mapping.append({'table':table_id,'key':key,'title':title,'sources':[register(p) for p in src],
                    'operation':operation,'rows':len(data),'display_columns':cols,
                    'machine_table':f'{table_id}_{key}.csv'})

def pairs(df, keycols):
    d=df[df.train_version.eq(df.score_version)].copy()
    cols=['average_precision','brier','roc_auc','retrospective_recall_at_5percent']
    a=d[d.train_version.eq('A')][keycols+cols].rename(columns={c:'A_'+c for c in cols})
    b=d[d.train_version.eq('B')][keycols+cols].rename(columns={c:'B_'+c for c in cols})
    x=a.merge(b,on=keycols,validate='one_to_one')
    x['delta_AP']=x.B_average_precision-x.A_average_precision
    return x

def showpairs(d, labels):
    z=pd.DataFrame({name:d[col].map(block) if col=='block' else d[col] for col,name in labels})
    for col,name,mult,digits in [('A_average_precision','AA AP (%)',100,3),('B_average_precision','BB AP (%)',100,3),('delta_AP','ΔAP (pp)',100,3),('A_brier','AA Brier',1,6),('B_brier','BB Brier',1,6)]:
        z[name]=d[col].map(lambda v:fmt(v,digits,mult))
    return z

cohort=pq(ROOT/'datasets/model_cohort.parquet')
assert len(cohort)==5502 and cohort.registry_event_365.sum()==188
cohort['year']=pd.to_datetime(cohort.decision_date).dt.year
annual=[]
for year,g in cohort.groupby('year'):
    pos=g[g.registry_event_365.eq(1)]
    annual.append(dict(year=year,landmarks=len(g),ciks=g.cik.nunique(),clusters=g.cluster_id.nunique(),weighted_landmarks=g.sample_weight.sum(),positive_windows=len(pos),event_ciks=pos.cik.nunique()))
annual=pd.DataFrame(annual)
make_table('annual','Annual eligible observations.',annual,annual.rename(columns={'year':'Year','landmarks':'N','ciks':'CIKs','clusters':'Clusters','weighted_landmarks':'Weighted N','positive_windows':'+ windows','event_ciks':'Event CIKs'}).assign(**{'Weighted N':annual.weighted_landmarks.map(lambda v:fmt(v,3))}),
           'N counts filing landmarks. Weighted N is expanded landmark mass, not an independent sample size. CIKs and clusters recur across years; their annual counts must not be summed to estimate distinct entities.',[ROOT/'datasets/model_cohort.parquet'],'Group frozen cohort by origin calendar year; sum design weights and direct-CIK labels.')

split=js(DC/'split_audit.json')
split=pd.DataFrame([{k:r.get(k) for k in ['block','stage','validation_year','n','positive_windows','n_cik','n_sampling_clusters','weighted_n']} for r in split if r['experiment']=='identical_input_tuned'])
make_table('splits','Temporal development denominators.',split,pd.DataFrame({'Block':split.block.map(block),'Stage':split.stage.str.replace('_',' '),'N':split.n,'+':split.positive_windows,'CIKs':split.n_cik,'Clusters':split.n_sampling_clusters,'Weighted N':split.weighted_n.map(lambda x:fmt(x,3))}),
           'Rows are identical for A and B. Final refit contains mature preliminary-training and validation observations; these stages are not disjoint samples.',[DC/'split_audit.json'],'Select identical_input_tuned stage audit, one row per block/stage.')

oldmetrics=csv(OLD/'results/models/metrics.csv')
dcmetrics=csv(DC/'metrics.csv')
four=csv(ED/'four_cell_decomposition_unrounded.csv')
ap=four[four.metric.eq('average_precision')].copy()
disp=pd.DataFrame({'Block':ap.block.map(block),'Learner':ap.model})
for c in ['AA','AB','BA','BB','input_AB_minus_AA','fit_BA_minus_AA','interaction','total_BB_minus_AA']:
    disp[{'input_AB_minus_AA':'I','fit_BA_minus_AA':'F','interaction':'J','total_BB_minus_AA':'Total'}.get(c,c)]=ap[c].map(lambda x:fmt(x,4,100))
make_table('four_cell','Complete tuned AP comparison.',ap,disp,'Cells are AP × 100; I, F, J and Total are percentage-point differences calculated before rounding. These are metric-level contrasts, not additive case contributions.',[ED/'four_cell_decomposition_unrounded.csv'],'Select AP; display exact independently recomputed four cells and contrasts.')

main=csv(ROOT/'results/models_20260921T093517075175Z_metrics.csv')
make_table('main_metrics','Original tuned probability and screening results.',main,pd.DataFrame({'Block':main.block.map(block),'Learner':main.model.replace({'PREVALENCE':'Constant'}),'Arm':main.version,'AP (%)':main.average_precision.map(lambda x:fmt(x,3,100)),'ROC':main.roc_auc.map(lambda x:fmt(x,4)),'Brier':main.brier.map(lambda x:fmt(x,6)),'Recall 5% (%)':main.retrospective_recall_at_5percent.map(lambda x:fmt(x,2,100))}),
           'AP, ROC and Brier use design weights. Recall uses 5% of each complete block’s weighted landmark mass, with fractional selection shared by all observations tied at the boundary. The constant probability is the mature refit prevalence.',[ROOT/'results/models_20260921T093517075175Z_metrics.csv'],'All original metrics, including constant reference; no filtering on outcome or performance.')
make_table('calibration','Held-out calibration diagnostics.',main,pd.DataFrame({'Block':main.block.map(block),'Learner':main.model.replace({'PREVALENCE':'Constant'}),'Arm':main.version,'CIL':main.calibration_intercept.map(fmt),'Joint intercept':main.calibration_joint_intercept.map(fmt),'Joint slope':main.calibration_slope.map(fmt)}),
           'CIL is calibration-in-the-large with slope fixed to one. Joint intercept and slope come from a separate fit. A dash denotes an unidentified joint slope/intercept for constant predictions. These fits diagnose saved probabilities and never update them.',[ROOT/'results/models_20260921T093517075175Z_metrics.csv'],'Use original held-out calibration estimates; retain constant-model missing estimates.')

tp=ROOT/'results/models_20260921T093517075175Z_tuning.jsonl';register(tp)
tuning=[]
for line in tp.read_text(encoding='utf-8').splitlines():
    r=json.loads(line)
    if r.get('stage')=='tuning':
        tuning.append(dict(block=r['block'],model=r['model'],version=r['version'],candidate=r['candidate'],parameters=json.dumps(r['parameters'],sort_keys=True),AP=r['metrics']['average_precision'],Brier=r['metrics']['brier']))
td=pd.DataFrame(tuning)
ta=td[td.version.eq('A')].drop(columns='version').rename(columns={'AP':'A_AP','Brier':'A_Brier'})
tb=td[td.version.eq('B')].drop(columns='version').rename(columns={'AP':'B_AP','Brier':'B_Brier'})
tv=ta.merge(tb,on=['block','model','candidate','parameters'],validate='one_to_one')
make_table('validation_grid','All original validation candidates.',tv,pd.DataFrame({'Block':tv.block.map(block),'Learner':tv.model,'Candidate':tv.candidate,'A AP (%)':tv.A_AP.map(lambda x:fmt(x,3,100)),'B AP (%)':tv.B_AP.map(lambda x:fmt(x,3,100)),'A Brier':tv.A_Brier.map(lambda x:fmt(x,6)),'B Brier':tv.B_Brier.map(lambda x:fmt(x,6))}),
           'Candidate 0–3: LR C = 0.01, 0.1, 1, 10; LightGBM (leaves, minimum leaf count) = (7,30), (7,60), (15,30), (15,60). These are validation results, not four independently refitted test comparisons for LR.',[tp],'Join A/B tuning records by block, learner, candidate and parameters. Absolute validation AP/Brier.')

fixed=pairs(dcmetrics[dcmetrics.experiment.str.startswith('grid_fixed_LGBM_')],['experiment','block','model'])
fixed['configuration']=fixed.experiment.map({'grid_fixed_LGBM_0':'7 / 30','grid_fixed_LGBM_1':'7 / 60','grid_fixed_LGBM_2':'15 / 30','grid_fixed_LGBM_3':'15 / 60'})
make_table('fixed_grid','Four common LightGBM configurations.',fixed,showpairs(fixed,[('block','Block'),('configuration','Leaves / min N')]),
           'Each configuration is fixed for both A and B, with separate preprocessing and fitted trees. Values are test results, not validation scores. Positive ΔAP favors BB for ranking only.',[DC/'metrics.csv'],'Select all grid_fixed_LGBM experiments and join AA/BB.')
alt=pairs(oldmetrics[oldmetrics.experiment.isin(['fixed_full','rolling_three_year','fixed_spline_rf'])],['experiment','block','model'])
alt['procedure']=alt.experiment.map({'fixed_full':'Fixed','rolling_three_year':'Rolling','fixed_spline_rf':'Diagnostic'})
make_table('alternative_learners','Other development procedures and learners.',alt,showpairs(alt,[('block','Block'),('model','Learner'),('procedure','Procedure')]),
           'Fixed LR uses C=1; fixed LightGBM uses 7 leaves/minimum count 30. Rolling selection has no first-block estimate because required folds fail class-availability rules. SPLINE_LR and RF are fixed diagnostic learners.',[OLD/'results/models/metrics.csv'],'All AA/BB for fixed_full, rolling_three_year and fixed_spline_rf; no best-result selection.')

ident=js(DC/'identical_input_audit.json')
idd=pd.DataFrame(ident['checks'])
make_table('identical','Identical-input controls.',idd,pd.DataFrame({'Block':idd.block.map(block),'Learner':idd.model,'Preprocess equal':idd.preprocessing_equal,'Grid equal':idd.all_four_candidate_metrics_equal,'Selection equal':idd.selection_equal,'Max score difference':idd.four_cell_max_abs_prediction_difference}),
           'B is replaced by A before independent execution of both paths, including tuning. Equality is computational equality in this environment, not a robustness claim for different data.',[DC/'identical_input_audit.json'],'All six block/learner checks.')
seeds=csv(DC/'algorithm_seed_summary.csv')
make_table('seeds','Prespecified seed checks on A.',seeds,pd.DataFrame({'Block':seeds.block.map(block),'Learner':seeds.model,'AP min (%)':seeds.AP_min.map(lambda x:fmt(x,3,100)),'AP max (%)':seeds.AP_max.map(lambda x:fmt(x,3,100)),'Brier min':seeds.Brier_min.map(lambda x:fmt(x,6)),'Brier max':seeds.Brier_max.map(lambda x:fmt(x,6)),'Max score span':seeds.max_prediction_range.map(lambda x:fmt(x,6))}),
           'Seeds are 20260921–20260925, under common fixed settings. LightGBM’s deterministic setup uses no row or feature subsampling; zero seed variation does not imply insensitivity to observations or weights.',[DC/'algorithm_seed_summary.csv',DC/'algorithm_seed_settings.json'],'All seed summaries; no distributional inference from five seeds.')

tr=csv(OLD/'results/models/transition_records.csv',dtype={'cik':str})
trrows=[]
for rid,g in tr.groupby('row_id',sort=False):
    r=g.iloc[0];stages=[]
    for i,b in enumerate(['2016_2017','2018_2019','2020_2021'],1):
        rr=g[g.block.eq(b)].iloc[0]
        stages += [f'{code}{i}' for field,code in [('in_original_tuning_train','T'),('in_original_validation','V'),('in_original_refit','F'),('in_original_test','E')] if rr[field]]
    trrows.append(dict(row_id=rid,cik=r.cik,origin=r.decision_date[:10],label=r.registry_event_365,missing=sum(pd.isna(r['A_'+c]) for c in ['log_assets','liabilities_to_assets','equity_to_assets','cash_to_assets','net_income_to_assets','revenue_to_assets','operating_income_to_assets','operating_cash_to_assets','retained_earnings_to_assets','working_capital_to_assets']),changed=r.n_changed_A_B,stages=', '.join(stages)))
trd=pd.DataFrame(trrows).sort_values('origin')
make_table('transition_records','Every transition-report landmark.',trd,trd.drop(columns='row_id').rename(columns={'cik':'CIK','origin':'Origin','label':'+','missing':'Missing','changed':'Changed','stages':'Stages'}),
           'Missing/Changed count the ten financial inputs. T: preliminary training; V: validation; F: final refit; E: test. Suffix 1/2/3 denotes chronological block. Outcomes link directly to CIK, never to all members of a sampling cluster.',[OLD/'results/models/transition_records.csv'],'Collapse three stage rows per landmark; retain every transition landmark.')
trans=pairs(oldmetrics[oldmetrics.experiment.isin(['transition_test_only','transition_development_tuned','transition_development_fixed','transition_both_saved'])],['experiment','block','model'])
trans['deletion']=trans.experiment.map({'transition_test_only':'Test only','transition_development_tuned':'Development/tuned','transition_development_fixed':'Development/fixed','transition_both_saved':'Both/tuned'})
make_table('transition_stage','Development and evaluation transition exclusions.',trans,showpairs(trans,[('block','Block'),('model','Learner'),('deletion','Deletion')]),
           'Test-only excludes test rows under saved original models; development-only preserves the original test set. Both excludes both domains. Fixed and tuned rows have different baselines and must not be interpreted as changes from one common reference.',[OLD/'results/models/metrics.csv'],'All four transition-stage experiments, both learners, all blocks.')
match=csv(DC/'matched_deletion_comparison.csv')
md=pd.DataFrame({'Block':match.block.map(block),'Learner':match.model,'Group':match.group.map({'positive_unchanged':'Positive unchanged','changed_negative':'Negative changed','other_unchanged_negative':'Negative unchanged'}),'AA (%)':match.transition_AA.map(lambda x:fmt(x,3,100)),'BB (%)':match.transition_BB.map(lambda x:fmt(x,3,100)),'Effect (pp)':match.transition_delta_change.map(lambda x:fmt(x,3,100)),'Matched median [min, max] (pp)':[f'{fmt(a,3,100)} [{fmt(b,3,100)}, {fmt(c,3,100)}]' for a,b,c in zip(match.ordinary_delta_change_median,match.ordinary_delta_change_min,match.ordinary_delta_change_max)],'At least as large (%)':match.ordinary_absolute_change_ge_transition_fraction.map(lambda x:fmt(x,0,100))})
make_table('matched_deletions','All transition-group and ordinary-deletion summaries.',match,md,
           'Effect is the deletion-induced change in BB−AA relative to the full-data common fixed baseline. For active group/block pairs there are 20 ordinary matched selections; the positive group is absent from the first two mature refit sets, giving no intervention and no matched distribution. The last column compares absolute changes descriptively; it is not a p-value.',[DC/'matched_deletion_comparison.csv',DC/'matched_deleted_weight_mass.csv',DC/'matched_selected_records.csv'],'All 18 group/block/learner summaries; preserve empty inactive comparisons.')

fit=csv(REV/'results/fit_date/fit_date_comparisons.csv')
fa=fit[fit.metric.eq('average_precision')].copy();fb=fit[fit.metric.eq('brier')]
fx=fa.merge(fb,on=['block','model'],suffixes=('_AP','_Brier'))
fd=pd.DataFrame({'Block':fx.block.map(block),'Learner':fx.model})
for prefix,title in [('original_A','A fit'),('fit_date','As-of fit'),('latest_B','Latest fit')]:
    fd[title+' AP (%)']=fx[prefix+'_train_A_score_AP'].map(lambda x:fmt(x,3,100))
    fd[title+' Brier']=fx[prefix+'_train_A_score_Brier'].map(lambda x:fmt(x,6))
make_table('fit_date','Filing-date restricted training, scored on A.',fx,fd,
           'All fits use original final-refit rows/weights and common fixed parameters. The as-of bundle is filed strictly before 1 January of the test block. Every test input is original A. This is current-API reconstruction by filing date, not a historically archived API snapshot.',[REV/'results/fit_date/fit_date_comparisons.csv'],'Join AP and Brier rows for three fits; no test-set domain change.')
cp=pairs(csv(DC/'CPI_domain_metrics.csv'),['experiment','block','model'])
cp['domain']=cp.experiment.map({'full_train_full_test':'Full / full','full_train_size_test':'Full / size','size_train_size_test':'Size / size'})
make_table('CPI_domains','Development and evaluation size domains.',cp,showpairs(cp,[('block','Block'),('model','Learner'),('domain','Train / test')]),
           'Size is defined once from original A assets and lagged current-series CPI. Full/size evaluates saved full-development models on the restricted test domain; size/size also changes development. These comparisons are not three independent replications.',[DC/'CPI_domain_metrics.csv'],'Join AA/BB in all three domain combinations, both learners and all blocks.')

ci=csv(ED/'independent_conditional_1000_summary.csv')
cid=[]
for (b,m),g in ci.groupby(['block','model']):
    rr={'Block':block(b),'Learner':m}
    for metric,title,mult,digits in [('average_precision','ΔAP (pp)',100,3),('brier','ΔBrier',1,6),('roc_auc','ΔROC',1,4),('retrospective_recall_at_5percent','ΔRecall (pp)',100,2)]:
        x=g[g.metric.eq(metric)].iloc[0];rr[title]=f'{fmt(x.delta,digits,mult)} [{fmt(x.ci95_low,digits,mult)}, {fmt(x.ci95_high,digits,mult)}]'
    cid.append(rr)
make_table('conditional_intervals','Original conditional 95% intervals.',ci,pd.DataFrame(cid),
           'Entries are BB−AA [lower, upper]. Basic-centered intervals use 1,000 paired design-weight draws with fitted models and certainty clusters fixed. They are pointwise conditional intervals, not full-pipeline or event-superpopulation uncertainty.',[ED/'independent_conditional_1000_summary.csv'],'Independent recomputation of original conditional draws; display all four metrics.')
mods=csv(ED/'perturbation_modes_distribution_summary.csv')
for metric,key,title,digits,mult in [('average_precision','AP_modes','AP distributions under three perturbation modes.',3,100),('brier','Brier_modes','Brier distributions under three perturbation modes.',6,1)]:
    mm=mods[mods.metric.eq(metric)].copy();dr=[]
    for (b,m,mode),g in mm.groupby(['block','model','mode']):
        mode_label=({'development_only':'Develop.','evaluation_only':'Eval.','joint':'Joint'}[mode]
                    if key=='Brier_modes' else mode.replace('_only','').replace('_',' '))
        rr={'Block':block(b),'Learner':m,'Mode':mode_label}
        for q in ['AA','BB','delta']:
            x=g[g.quantity.eq(q)].iloc[0]
            rr[{'AA':'AA','BB':'BB','delta':'Δ'}[q]]=f'{fmt(x.q50,digits,mult)} [{fmt(x.q5,digits,mult)}, {fmt(x.q95,digits,mult)}]'
            if q=='delta':rr['Δ > 0 (%)']=fmt(x.positive_fraction,1,100)
        dr.append(rr)
    make_table(key,title,mm,pd.DataFrame(dr),
               ('AP levels are percentages and differences are percentage points. ' if metric=='average_precision' else 'Brier uses its original probability-error scale; positive Δ indicates worse BB probability error. Mode abbreviations: Develop., development-only; Eval., evaluation-only; Joint, joint perturbation. ')+ 'Entries are median [5th, 95th empirical percentile], from 200 paired replicates. These are perturbation summaries, not nominal confidence intervals. All AA/BB/Δ summaries, additional quantiles, ROC and recall are retained in the machine-readable distribution table.',[ED/'perturbation_modes_distribution_summary.csv'],'Select metric; retain AA, BB and delta for all three modes, both learners and all blocks.')

event=csv(OLD/'results/uncertainty/event_cluster_leave_one_out_summary.csv',dtype={'largest_absolute_influence_ciks':str})
es=event[event.analysis_mode.eq('refit_vintages') & event.metric.isin(['average_precision','retrospective_recall_at_5percent'])].copy()
make_table('event_influence','Positive-associated cluster deletion under fixed predictions.',es,pd.DataFrame({'Block':es.block.map(block),'Learner':es.model,'Metric':es.metric.map({'average_precision':'AP','retrospective_recall_at_5percent':'Recall 5%'}),'Clusters':es.positive_bearing_clusters_deleted,'Original Δ (pp)':es.baseline_difference_B_minus_A.map(lambda x:fmt(x,3,100)),'Minimum Δ (pp)':es.minimum_difference.map(lambda x:fmt(x,3,100)),'Maximum Δ (pp)':es.maximum_difference.map(lambda x:fmt(x,3,100)),'Sign changes':es.strict_sign_reversals}),
           'Each deletion removes all test rows of one positive-associated sampling cluster; neither fitted pipeline is retrained. Capacity thresholds and metrics are recomputed on the remaining test population.',[OLD/'results/uncertainty/event_cluster_leave_one_out_summary.csv'],'Select main refit-vintage prediction comparison; AP and recall for every block/learner.')
score=csv(OLD/'results/uncertainty/score_rank_group_summary.csv')
sc=score[score.label_group.eq('all') & score.input_group.ne('all')].copy()
make_table('score_propagation','Score and rank propagation by input change.',sc,pd.DataFrame({'Block':sc.block.map(block),'Learner':sc.model,'Comparison':sc.analysis_mode.map({'refit_vintages':'Refit','frozen_A_inputs':'Frozen A'}),'Inputs':sc.input_group.map({'inputs_changed':'Changed','inputs_unchanged':'Unchanged'}),'N':sc.raw_rows,'Score changed (%)':sc.weighted_score_changed_fraction.map(lambda x:fmt(x,2,100)),'Rank changed (%)':sc.weighted_rank_changed_fraction.map(lambda x:fmt(x,2,100)),'Mean abs Δp':sc.absolute_score_difference_weighted_mean.map(lambda x:fmt(x,6))}),
           'Percentages and means use each displayed group’s design-weighted denominator. Numerical score change uses absolute difference >10⁻¹². Rank changes reflect weighted midrank movement and can occur for unchanged individual scores when other observations move. Subgroup AP is not summed to explain total AP.',[OLD/'results/uncertainty/score_rank_group_summary.csv'],'Select both comparisons and both input groups, pooled recorded outcomes; every block/learner.')

caps=[]
for h in [90,365,730]:
    cc=csv(OLD/f'results/cap_models/{h}/metrics.csv')
    dd=pairs(cc,['experiment','block','model']);dd['cap']=h;caps.append(dd)
cap=pd.concat(caps,ignore_index=True)
make_table('cap_metrics','Absolute finite-horizon version results.',cap,showpairs(cap,[('block','Block'),('model','Learner'),('cap','Days')]),
           'Common fixed configurations and the full original cohort are retained. B selects a coherent later bundle no later than origin plus the displayed horizon, or falls back to A. Even the shortest cap can include post-origin information and is not a deployable contemporaneous input.',[OLD/f'results/cap_models/{h}/metrics.csv' for h in [90,365,730]],'AA/BB for every capped experiment, both learners, all blocks.')
adj=csv(ED/'adjacent_horizon_summary.csv',dtype={'label':str});ad=adj[adj.domain.eq('full_cohort') & adj.label.eq('all')].copy()
make_table('cap_transitions','Adjacent source-horizon changes.',ad,pd.DataFrame({'Horizon':ad.transition,'New bundle':ad.newly_available_n,'Existing source switch':ad.existing_bundle_accession_switch_n,'Raw changed N':ad.raw_components_changed_tolerance_landmarks_n,'Feature changed N':ad.model_features_changed_landmarks_n,'Same-source value changes':ad.same_source_raw_values_changed_n}),
           'N counts affected landmarks, not component cells. New availability and source switching are distinct operations. No bundle is lost and no selected identical source changes its raw value within this frozen extraction.',[ED/'adjacent_horizon_summary.csv'],'Full cohort, all outcomes; use declared numerical tolerance for raw changes.')
ex=csv(ED/'version_exposure_summary.csv')
make_table('exposure_covariates','Exposure groups, original observability and subsequent filing.',ex,pd.DataFrame({'Domain':ex.domain.map(block),'Y':ex.label,'Exposure':ex.exposure_group.replace({'no_later_bundle':'No later','later_without_raw_change':'Later/same','later_with_raw_change':'Later/changed'}),'N':ex.raw_n,'Within Y (%)':ex.within_label_weighted_fraction.map(lambda x:fmt(x,2,100)),'Missing raw mean':ex.A_missing_raw_components_weighted_mean.map(lambda x:fmt(x,2)),'A assets median ($m)':ex.A_assets_weighted_median.map(lambda x:fmt(x/1e6,2)),'Next annual (%)':ex.continuity_within_known_weighted_fraction.map(lambda x:fmt(x,2,100))}),
           'Within-Y percentages use the full domain/outcome design-weighted denominator; covariates and continuation are weighted within exposure group. Next annual means an original 10-K/10-KT filed strictly after origin through origin + 365 days. It is retrospective reporting continuity, not verified survival. All intervals have resolved cache coverage.',[ED/'version_exposure_summary.csv',ED/'continuity_cache_audit.json'],'All full-cohort and test-block outcome/exposure cells, without selecting successful reporters for eligibility.')
mag=csv(ED/'raw_component_magnitude_summary.csv');sg=csv(ED/'raw_component_sign_categories.csv')
fold=mag[mag.subset.eq('same_sign_nonzero_changed') & mag.measure.eq('multiplicative_fold')].copy()
amp=mag[mag.subset.eq('changed_pairs') & mag.measure.eq('original_relative_amplitude')][['feature','weighted_q50','weighted_q95']].rename(columns={'weighted_q50':'amplitude_median','weighted_q95':'amplitude_q95'})
fl=sg[sg.sign_category.eq('sign_flip')][['feature','raw_n']].rename(columns={'raw_n':'sign_flips'})
ma=fold.merge(amp,on='feature').merge(fl,on='feature')
make_table('magnitude','Raw-component magnitude and sign diagnostics.',ma,pd.DataFrame({'Component':ma.feature.str.replace('_',' '),'Same-sign changed N':ma.raw_n,'Median fold':ma.weighted_q50.map(lambda x:fmt(x,3)),'95th fold':ma.weighted_q95.map(lambda x:fmt(x,3)),'Max fold':ma['max'].map(lambda x:fmt(x,3)),'Sign flips':ma.sign_flips,'Bounded median':ma.amplitude_median.map(lambda x:fmt(x,4)),'Bounded 95th':ma.amplitude_q95.map(lambda x:fmt(x,4))}),
           'Fold = max(|B/A|, |A/B|) among changed, same-sign, nonzero pairs. Sign flips are raw counts among all observed pairs and are excluded from fold summaries. The retained amplitude is |B−A| / max(1, |A|, |B|); its changed-pair denominator also includes sign/zero cases. These are numerical discrepancies, not certified errors.',[ED/'raw_component_magnitude_summary.csv',ED/'raw_component_sign_categories.csv'],'Join same-sign changed fold, all changed-pair amplitude, and sign-flip counts by component.')

scale=csv(REV/'results/scale_only/metrics.csv');disputed=csv(OLD/'results/corrected_models_v2/metrics.csv')
sp=pairs(scale,['experiment','block','model']);sp['evidence']='Scale22'
dp=pairs(disputed,['experiment','block','model']);dp['evidence']='Joint26*'
cor=pd.concat([sp,dp],ignore_index=True);cor['procedure']=cor.experiment.str.replace('source_corrected_','',regex=False)
make_table('source_sensitivity','Source-adjustment evidence levels.',cor,showpairs(cor,[('block','Block'),('model','Learner'),('procedure','Procedure'),('evidence','Adjustment')]),
           'Scale22 uses 22 keys supported by displayed statement units; Joint26* is the older exercise additionally applying four unresolved sign proposals. Neither is authenticated original-instance XBRL or completed human expert certification. This preserves the disputed scenario without treating its changes as verified corrections.',[REV/'results/scale_only/metrics.csv',OLD/'results/corrected_models_v2/metrics.csv'],'Retain all AA/BB tuned and fixed results for both evidence sets.')

# Full-precision working tables supplement the formatted document, especially
# the metrics not expanded into a second repetitive printed table.
for name,path in [('all_modes',ED/'perturbation_modes_distribution_summary.csv'),('all_four_cells',ED/'four_cell_decomposition_unrounded.csv'),('matched_selections',DC/'matched_selected_records.csv'),('matched_weight_mass',DC/'matched_deleted_weight_mass.csv'),('source_stage_trace',REV/'results/source_semantics/source_keys_to_components_features_stages.csv'),('candidate_changes',OLD/'results/uncertainty/candidate_pair_selection_summary.csv')]:
    frame=csv(path)
    frame.to_csv(OUT/f'record_{name}.csv',index=False)

# Explicit evidence map for numerical prose outside the tables.
sf=js(ROOT/'results/sampling_frame_summary.json')
us=js(ROOT/'results/universe_summary.json')
cs=js(ROOT/'results/cohort_summary.json')
continuity=js(ED/'continuity_cache_audit.json')
fc=csv(REV/'results/fit_date/fit_date_coverage.csv')
timing=csv(ED/'training_B_source_timing_summary.csv')
after=timing[timing.category.eq('later_after_fit')]
plan=js(DC/'matched_deletion_plan.json')
selected=csv(DC/'matched_selected_records.csv')
scalef=csv(REV/'results/scale_only/changed_features.csv')
scales=csv(REV/'results/source_semantics/scale22_prediction_effect_summary.csv')
claims={'sampling':sf,'historical_frame':us,
        'cohort':{'rows':len(cohort),'ciks':cohort.cik.nunique(),'clusters':cohort.cluster_id.nunique(),'positive_windows':int(cohort.registry_event_365.sum()),'negative_windows':int((cohort.registry_event_365==0).sum())},
        'continuity':continuity['statuses'],
        'fit_date_coverage':fc.to_dict('records'),
        'fit_date_timing':timing.to_dict('records'),
        'matched_plan_status_counts':pd.Series([x['status'] for x in plan]).value_counts().to_dict(),
        'matched_positive_unique_selected':selected[selected.group.eq('positive_unchanged')].selected_row_id.nunique(),
        'matched_positive_pool_sizes':selected[selected.group.eq('positive_unchanged')].candidate_pool_n.unique().tolist(),
        'scale_feature_cells_by_arm':scalef.arm.value_counts().to_dict(),
        'scale_max_prediction_change':scales.groupby(['comparison','model']).max_abs_delta.max().reset_index().to_dict('records')}
assert claims['cohort']=={'rows':5502,'ciks':990,'clusters':973,'positive_windows':188,'negative_windows':5314}
assert cohort[cohort.registry_event_365.eq(1)].cik.nunique()==188
assert after.raw_n.tolist()==[6,8,6] and after.model_input_changed_landmarks.tolist()==[3,6,2]
assert continuity['statuses']=={'observed_presence':3330,'covered_no_annual_filing':2172}
assert mods.valid_n.eq(200).all() and mods.n.eq(200).all()
assert ci.valid_replicates.eq(1000).all()
assert len(td)==48 and len(tv)==24 and len(fixed)==12
assert len(trd)==12 and len(match)==18 and len(ma)==11
assert scalef.arm.value_counts().to_dict()=={'C':6,'A':1,'B':1}
assert scales[scales.model.eq('LGBM')].max_abs_delta.eq(0).all()
assert claims['matched_plan_status_counts']=={'ready':140,'inactive_no_development_record':40}
assert claims['matched_positive_unique_selected']==15 and claims['matched_positive_pool_sizes']==[30]
assert all(len(pd.read_csv(OUT / item['machine_table']))==item['rows'] for item in mapping)
for f in [ROOT/'scripts/build_vintage_panel.py',ROOT/'scripts/run_vintage_models.py',ROOT/'scripts/uncertainty_vintage.py',OLD/'scripts/revision_models.py',OLD/'scripts/revision_uncertainty.py',REV/'scripts/evaluation_diagnostics.py',REV/'literature/manuscript_source_notes.md']:
    register(f)
(OUT/'narrative_numeric_claims.json').write_text(json.dumps(claims,indent=2,ensure_ascii=False,default=lambda v:int(v) if isinstance(v,np.integer) else str(v)),encoding='utf-8')

BODY = r'''---
title: 'Supplementary Methods and Results'
---

This document specifies the implemented comparison, preserves absolute results, and separates diagnostics with different inferential targets. AP denotes average precision; LR denotes logistic regression; LGBM denotes LightGBM; AA and BB denote matching fitted and scored financial versions. AP levels are displayed as percentages and AP differences as percentage points unless stated otherwise. Brier scores remain on their original probability-error scale. Tables are generated from saved numerical outputs before rounding. The accompanying data retain full precision, all cross-scoring cells, detailed denominator fields and a table-to-source mapping.

## S1. Sampling frame, observation unit and recorded outcome

The historical frame comprises original 10-K and 10-KT metadata for 2010–2021. It contains 93,677 company–filing records, 90,338 accessions and 15,631 CIKs. A shared accession creates an edge between CIKs; connected components define 14,929 sampling clusters. These are observable cofiling relationships, not independently reconstructed legal groups. All 383 clusters containing a direct BRD identifier are included. Of the remaining 14,546 clusters, 1,000 are selected without replacement under the frozen seed. Every member inherits its cluster inclusion probability. The sample contains 1,518 CIKs, including 438 certainty-stratum identifiers; inverse probabilities are 1 and 14.546. Multiple eligible observations inherit the same cluster weight [@horvitz1952].

The sampling frame is independent of a current ticker list. Its annual form counts agree with the archive comparison in 48 year–form cells. An additional convenience check covers 1,780 official records from 162 CIKs. Agreement establishes consistency for those checks, not exhaustive historical authentication. Sampling weights do not repair unavailable companyfacts, failed identifier links, custom-tag coverage or the exclusion of observations without positive original assets. The sequential attrition in the main article therefore defines the accessible analysis domain; the expanded weight total is not the population of all US businesses.

A landmark is the first original annual accession for a CIK and fiscal end, with origin on the following day. It must match the historical frame, have an origin in 2010–2021, precede the first directly linked BRD event, contain positive original assets and have nonnegative reporting delay. Positive status means that first direct-CIK event falls strictly after origin and no more than 365 days later. A zero means no matching registry event in that interval. It is not independently adjudicated absence of every bankruptcy, insolvency or cessation event. BRD covers large public-company cases through 2022; its inflation-adjusted size and reporting-history criteria are narrower than the SEC annual-filer frame. Events are never propagated from one CIK to its cofiling neighbours.

The final cohort contains 5,502 landmarks, 990 CIKs and 973 sampling clusters. Its 188 positive windows link to distinct event CIKs; this does not certify 188 independent corporate-group cases. Annual counts below distinguish landmarks, weighted mass and recurring entities.

{{annual}}

## S2. Accounting extraction and matched financial versions

The extraction uses standard US GAAP concepts under the USD unit. The following hierarchy is searched in order. An ambiguous selected candidate stops extraction for that component; a later alternative tag is not used to conceal ambiguity.

- Assets: `Assets`.
- Liabilities: `Liabilities`.
- Equity: `StockholdersEquity`, then `StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest`.
- Cash: `CashAndCashEquivalentsAtCarryingValue`, then `CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents`.
- Current assets and current liabilities: `AssetsCurrent` and `LiabilitiesCurrent`.
- Net income: `NetIncomeLoss`, then `ProfitLoss`.
- Revenue: `Revenues`, `RevenueFromContractWithCustomerExcludingAssessedTax`, `SalesRevenueNet`, then `SalesRevenueGoodsNet`.
- Operating income: `OperatingIncomeLoss`.
- Operating cash flow: `NetCashProvidedByUsedInOperatingActivities`.
- Retained earnings: `RetainedEarningsAccumulatedDeficit`.

For A, accession and end date must match the original filing, and the fact’s filed date cannot exceed that filing date. Instant facts have no start date. Net income, revenue, operating income and operating cash flow require a duration of 330–400 days. Identical duplicate signatures collapse; multiple starts or distinct values under the selected accession/concept remain ambiguous. The procedure can therefore retain instant facts from a short transition filing while leaving annual flows missing.

For component $j$ initially observed at landmark $i$, let $\mathcal C_{ij}(h)$ contain later accessions with the same concept, USD unit, start and end, a unique matched value, and filing date no later than horizon $h$. Coherent replacement requires the intersection

$$\mathcal C_i(h)=\bigcap_{j\in J_i}\mathcal C_{ij}(h).$$

The selected accession maximizes filing date, with accession order breaking equal-date ties. The main latest horizon is 21 September 2026. An empty intersection produces whole-vector fallback to A. Components absent in A stay absent. The descriptive per-component latest alternative, C, can mix accessions and is not an evaluation arm. Accepted later forms include annual, amended annual, quarterly and relevant transition forms; a later comparative need not appear only in another annual report.

Ten financial inputs are log assets, eight component/assets ratios, and working capital/assets. Working capital is current assets minus current liabilities. The eight ratios use liabilities, equity, cash, net income, revenue, operating income, operating cash flow and retained earnings. Each version uses its own assets denominator. Original reporting delay is shared across arms. Eleven explicit missingness flags accompany the eleven numerical predictors. This preserves initial observability rather than making later availability an eligibility condition. Accession association reconstructs current API records; it does not authenticate the historical content of an API response at origin or prove that every numerical change is an error correction [@sec_api; @sec_financial_datasets].

## S3. Temporal development and preprocessing

For a test block beginning on 1 January of year $t$, validation uses calendar year $t-3$. A development label is mature when origin plus 455 days is on or before the relevant fitting boundary: a 365-day outcome window plus an assumed 90-day administrative buffer. The buffer is not an observed registry-publication lag. Preliminary training precedes validation and satisfies maturity at validation start. Final refitting uses all observations mature at test start. The three test blocks cover 2016–2017, 2018–2019 and 2020–2021. Test observations do not supply preprocessing, selection or recalibration parameters.

Each training partition estimates design-weighted first/99th percentile clipping thresholds, median imputations and, for logistic models, means and scales. Weighted quantiles invert the empirical weighted distribution. Variables entirely missing in training receive numerical zero; near-zero scales are replaced by one. The fitted transform is carried unchanged when a model scores another financial version. Fitting weights are divided by their training mean, while evaluation retains the original design weights. There is no class balancing, oversampling or synthetic minority generation. Consequently, weight perturbation can alter clipping and imputation as well as the classifier.

{{splits}}

The first preliminary sample contains only three positive windows and its validation year seven. Its selection is therefore treated as exploratory sparse-event development, rather than evidence of a precisely identified model ranking. Rolling selection, added after the original results, averages weighted validation AP equally over years $t-5$ through $t-3$. Every prescribed training and validation fold must contain both classes. The earliest block is unavailable because these requirements fail; missing folds are not replaced with favourable later years.

## S4. Complete original evaluations and model selection

For fitted version $u$ and scored version $v$, $P_{uv}$ denotes the same metric computed on the same test observations. The fitted object includes preprocessing and candidate selection. Input substitution, fitted-pipeline change and interaction are

$$I=P_{AB}-P_{AA},\qquad F=P_{BA}-P_{AA},\qquad J=P_{BB}-P_{BA}-P_{AB}+P_{AA}.$$

Then $P_{BB}-P_{AA}=I+F+J$. This is an arithmetic organization of four procedural evaluations, not a new causal identification result or a decomposition of AP across companies. Independent recomputation from saved predictions agrees with the stored metrics to floating-point tolerance; contrasts below are formed before display rounding.

{{four_cell}}

Weighted AP follows the grouped-score average-precision definition, rather than trapezoidal precision–recall area. Weighted ROC uses concordance with equal treatment of score ties. Brier is the weighted mean squared probability error. Retrospective recall ranks the complete two-year block and selects 5% of total weighted landmark mass. Every score tie at the capacity boundary receives the same fraction. This is not a live policy ranking a simultaneously available company universe [@saito2015; @gneiting2007].

{{main_metrics}}

Calibration is descriptive and never feeds back into these predictions. Calibration-in-the-large solves an intercept-only recalibration equation with slope fixed to one. A separate weighted logistic fit estimates a free intercept and slope against the prediction logit. Constant predictions do not identify a joint slope. Optimizer, separation and information-matrix diagnostics remain in the numerical records. Apparent ranking improvement must not be equated with calibrated probabilities: the original tuned LightGBM BB Brier exceeds AA in every block, and both arms exceed the constant reference in the final two blocks.

{{calibration}}

The original LR grid uses $C=0.01,0.1,1,10$. LightGBM crosses 7/15 leaves with minimum leaf counts 30/60, using 300 trees and learning rate 0.05. Weighted validation AP determines the candidate; exact ties follow grid order. The table reports every original candidate, including low absolute performance, rather than only the selected configurations. Validation and final-test results remain separate objects.

{{validation_grid}}

## S5. Fixed configurations, additional learners and computation controls

The common fixed LR configuration is $C=1$; common fixed LightGBM uses seven leaves and minimum leaf count 30. An additional control refits all four original LightGBM configurations on the complete mature development sample, holding each configuration equal across versions. It removes independent candidate selection without forcing learned preprocessing or model parameters to be equal. The absolute results show why a sign change cannot be interpreted solely from the tuned diagonal contrast.

{{fixed_grid}}

The additive spline model transforms each winsorized/imputed numerical input with cubic B-splines. Knots are distinct training-weighted quantiles at 0.05, 0.35, 0.65 and 0.95. Constant columns remain linear; extrapolation is linear, there are no interactions, missingness flags remain explicit, the basis is training-weight standardized, and logistic regularization is $C=1$. The random forest uses 400 trees, depth six, minimum leaf size 20 and square-root feature sampling. These are diagnostic functional forms with declared fixed settings, not a claim to have optimized or comprehensively benchmarked bankruptcy prediction.

{{alternative_learners}}

The identical-input test independently runs both pipelines after replacing B by A. It compares preprocessing, all four validation candidates, selection and four-cell predictions. Every check is equal. This rules out an observed procedural asymmetry for identical inputs in this implementation, while leaving sensitivity to different training values and samples open.

{{identical}}

Five fixed seeds assess ordinary algorithmic randomness on A. LightGBM is deterministic with column-wise processing, unit row/feature sampling fractions and no bagging frequency. Its training sets are below the bin-sampling threshold. Changing its seed therefore creates no substantive stochastic intervention; zero variation must not be presented as broad algorithmic stability. Random-forest variation supplies a separate stochastic reference.

{{seeds}}

## S6. Transition observations and matched development perturbations

All 12 transition landmarks are retained below. The original exclusion mixed development and evaluation changes. Revised comparisons therefore separate test-only removal under archived models, development-only removal with the complete original test set, and removal from both stages. The two 2021 transition test rows are negative; excluding them yields a very small final-block AP difference that rounds to the original value, not exact equality. Development-stage effects remain possible even when an influential record has identical A/B inputs.

{{transition_records}}

{{transition_stage}}

Transition observations are partitioned into one unchanged positive, two changed negatives and nine other unchanged negatives. Group deletion removes only mature development members, under common fixed LR and LightGBM configurations; test rows stay fixed. The positive landmark is not in the first two mature refit samples, so those are explicitly zero-intervention comparisons. An unchanged positive can influence later training without representing a corrected accounting value.

Ordinary deletion matches each active target on origin year, outcome and the original three-bit preliminary-training/validation/final-refit membership. There is no approximate matching fallback. Twenty fixed selections are generated per active group/block, without replacement within a selection; observations may recur across selections. The design yields 140 valid matched selections and 40 inactive planned comparisons, with no pool-shortage substitution. Matching does not fix sampling stratum or deleted weight mass. Negative observations can carry weight 1 or 14.546, a material residual difference retained in the weight-mass audit. The positive matching pool contains 30 eligible records; 20 selections use 15 distinct records.

{{matched_deletions}}

The reference distributions are descriptive and overlapping, not null samples or p-values. Several transition effects lie within ordinary perturbation ranges. However, removal of the other unchanged-negative group in the middle block has a larger absolute LightGBM contrast change than all 20 matched selections. It would therefore be inaccurate to claim that every transition influence is fully explained by ordinary deletion variability. These results localize sensitivity; they do not establish that all transition filings are erroneous, or that matched deletions are an exhaustive alternative explanation.

## S7. Training information dates and size-domain controls

The fit-date exercise separates the landmark’s scoring date from the model’s final-refit date. For each block, a training row uses the latest coherent bundle filed strictly before the block’s 1 January fitting boundary, with original A fallback. Same-day filings are not ordered within a day. Rows, labels, weights, masks and common fixed parameters remain unchanged, and every test observation is scored on A. This distinguishes a permissible filing-date training update from latest comparative information that became available after model fitting. It still relies on current API extraction, not archived historical API states.

Only 6, 8 and 6 unlimited-B training sources are later than the respective fitting boundaries, representing approximately 0.216%, 0.342% and 0.190% of all refit weight. They are not all unchanged: 3, 6 and 2 rows respectively have changed numerical model inputs. Most later-than-origin training comparatives precede model fitting. The distinction matters because small source-date differences can affect nonlinear development even when the affected weighted share is small.

{{fit_date}}

The size proxy uses original assets exceeding $100 million multiplied by lagged CPI-U divided by the 1980 annual average of 82.4. CPI is taken from two months before origin, using the current non-seasonally-adjusted historical series. It is not an authenticated CPI vintage or complete BRD eligibility reconstruction. Full/full, full/size and size/size comparisons respectively preserve both domains, restrict only evaluation, or restrict development and evaluation. They retain common fixed configurations. Restricting only test observations reuses saved models; it does not refit on the smaller domain. All positive test windows remain under this proxy, while weighted prevalence changes substantially through the negative denominator.

{{CPI_domains}}

In the middle block, the full/size LightGBM contrast remains positive, whereas size/size is negative. Thus the large reversal cannot be attributed merely to recalculating metrics after removing smaller test companies. It accompanies a development-domain intervention. This is a controlled computational comparison inside one historical dataset, not evidence of a general size-specific financial mechanism.

## S8. Conditional sampling intervals and paired pipeline perturbations

The conditional intervals retain all 1,000 probability-sampled clusters, including clusters with no eligible observation in a particular test block. Certainty clusters stay fixed. With $n=1000$, $N=14546$, and multinomial count $M_g$ from $n-1$ equiprobable draws, the finite-population rescaled multiplier is

$$r_g=1+\sqrt{1-n/N}\left(\frac{nM_g}{n-1}-1\right),\qquad w_i^*=w_i r_{g(i)}.$$

The same multiplier follows all observations of cluster $g$ across time and both versions. Certainty multipliers equal one. The 1,000 conditional draws hold fitted predictions fixed, recompute all weighted metrics and capacity thresholds, and construct basic-centered pointwise intervals [@raowu1988; @raowuyue1992]. They quantify sampling of the probability stratum conditional on the observed certainty events and models. They exclude model development uncertainty, registry omissions, future economies and event-superpopulation variability.

{{conditional_intervals}}

The subsequent 200 paired perturbations re-estimate clipping, imputation, scaling, all candidate fits, selection and final refitting, with a common replicate across the two versions. Their fixed count and seed were chosen before inspecting these distributions. The present diagnostic reuses those saved models’ predictions and multipliers; it adds no training. Development-only pairs the replicate models with original evaluation weights; evaluation-only pairs original models with replicate weights; joint uses both replicate models and replicate weights. A replicate number identifies the same perturbation across modes. AA, BB and their difference are all preserved.

{{AP_modes}}

{{Brier_modes}}

These distributions are coupled nonlinear functionals. Their variances cannot be added to decompose a total variance, and positive fractions are not posterior probabilities or probabilities of replication. The 200-draw summaries are presented as perturbation distributions, not precise nominal intervals. Candidate selection and AP are nonsmooth. Positive rescaled weights also differ from physically duplicating observations: tree bin construction and minimum leaf-count constraints do not become fully equivalent under weighting. All modes share a fixed certainty stratum, so the three chronological blocks should not be counted as independent macroeconomic experiments. Complete ROC/recall distributions and 2.5th, 25th, 75th and 97.5th percentiles remain in the numerical supplement.

## S9. Event influence and prediction propagation

Each positive-associated cluster is removed once from the relevant test block, together with all its test trajectories. Stored fitted models are held fixed. Recomputed weighted capacity thresholds and metrics show how one observed event-bearing cluster affects the comparison; this is not a refit after event deletion and not an uncertainty interval for new bankruptcy cases.

{{event_influence}}

The final LightGBM AP contrast crosses slightly below zero after removing its most influential cluster, rather than producing a large opposite effect. The associated RTW Retailwinds landmark has unchanged A/B inputs. Its influence therefore concerns learned scores and the evaluation event set, not evidence that its source value changed or was erroneous. Frozen-A scoring and full refitting must remain separate when interpreting the associated score and rank movement.

{{score_propagation}}

After refitting, a prediction may change even when that row’s input is identical because its fitted preprocessing or model changed. Conversely, a score can remain identical under frozen-A substitution yet move in rank when other observations’ scores change. Within-group score and rank summaries describe these channels without assigning additive pieces of AP to groups. A claim about the fraction of changed probabilities must identify the learner, comparison, tolerance and denominator; it cannot be expanded into a statement that every raw accounting input changed.

## S10. Availability horizons, exposure and numerical magnitude

Finite horizons of 90, 365 and 730 days after origin preserve coherent matching and whole-vector fallback. Their absolute results are reported under common fixed configurations. Each can include information disclosed after origin, so none is labelled a contemporaneous deployable score. A horizon increase may create the first complete later bundle or replace an already available bundle. Those operations are counted separately, including raw-component and derived-input changes.

{{cap_metrics}}

{{cap_transitions}}

Exposure separates no coherent later bundle, a later bundle with unchanged raw components, and a later bundle with at least one numerical difference. Differences obey

$$|B-A|>10^{-12}\max(1,|A|,|B|).$$

Eligibility never depends on future reporting. Exposure itself is retrospective and may associate with outcome, company size, missingness and later filing. The full-cohort outcome denominators are 188 positive and 5,314 other windows. Weighted percentages below condition on the displayed domain and recorded outcome; covariate summaries condition further on exposure group. They must not be read as risk probabilities for firms with no later filing.

{{exposure_covariates}}

Subsequent annual filing is observable from cached official submissions and historical-file metadata. Presence means an original 10-K/10-KT strictly after origin and within 365 days. An unresolved historical-file gap would make absence unknown, rather than zero; all cohort intervals have resolved coverage in the retrieved cache. Of the cohort, 3,330 intervals contain a subsequent annual filing and 2,172 do not within that particular window. A crosscheck against the historical master frame agrees for all 5,093 intervals fully covered by that frame. The remaining intervals require subsequent official metadata. This describes a dated filing process, not permanent exit, survival or an independently observed bankruptcy label.

For same-sign nonzero raw pairs, multiplicative change is $\log_{10}(|B/A|)$; its absolute value and corresponding fold retain changes obscured by bounded amplitude. Sign flips and zero cases have separate denominators. The earlier bounded measure, $|B-A|/\max(1,|A|,|B|)$, is retained for continuity. Neither a large fold nor a sign flip alone establishes data error; changes in scope or accounting presentation can also generate them.

{{magnitude}}

## S11. Source evidence and adjustment boundaries

The probability source audit selects two test landmarks from each block × outcome × raw-change stratum, giving 24 sampling units. The secondary fact is selected by a declared within-landmark rule and does not create an independent additional sampling unit. Six purposive examples and subsequent targeted development checks have separate roles; they cannot be merged into the probability sample to estimate discrepancy prevalence. Displayed statement agreement, issuer-instance XBRL authentication, semantic interpretation and human expert confirmation are separate evidence layers.

The present supported adjustment set contains 22 Nobilis source keys supported by displayed thousand-unit statements. They affect two A/B numerical feature cells, both log assets, while six further changed feature cells belong to descriptive C. Uniform scale changes cancel in the corresponding ratios. Four sign proposals are unresolved because an issuer instance/context/presentation chain has not been authenticated; rendering a negative amount does not alone identify the correct element sign [@secNegativeValues2017]. The old 26-key calculation is preserved as a disputed sensitivity, never described as 26 verified corrections.

{{source_sensitivity}}

Independent saved-prediction checks find no LightGBM score change under the 22 scale-supported keys in either tuned or fixed comparisons. LR maximum individual changes are approximately 0.002534 and 0.001826 respectively. The larger LightGBM effects in the older joint exercise therefore accompany the unresolved sign interventions; they cannot establish effects of certified source errors. Source keys map explicitly to accession, concept, unit, dates, component, feature, landmark and development/test stage in the trace table.

The two changed transition examples also differ substantively. Rentech discloses a historical income-tax-liability correction; Silver Stream’s reports reflect a reverse-takeover change in accounting predecessor. Gymboree’s event-positive transition observation has unchanged selected instant components. These examples qualify a blanket “bad transition data” explanation. All source assessment remains AI assisted, with no completed independent human accounting approval or original-instance XBRL authentication. The accompanying source notes and pending-sign ledger retain these unresolved tasks.

## S12. Scope of contribution and reproducibility

Original-versus-restated bankruptcy inputs have prior precedent. Hashemi and Jonsson’s institutional master’s thesis compares such inputs in fixed accounting models within an SEC-enforcement sample; it is not a verified peer-reviewed prediction benchmark [@hashemi2017]. The contribution here must therefore rest on the executable separation of source coherence, fitting time, scoring time, development procedure and evaluation population, with explicit uncertainty boundaries. Arithmetic four-cell identities, transparent code and a large number of sensitivity fits are not by themselves novel statistical theory or independent replication.

The original protocol was frozen after feasibility analysis but before full original scoring results were inspected. All revisions, including source, candidate, deletion, domain and perturbation controls, were added with the original outcomes known. Their internal plans and row selections improve auditability but do not make them preregistered or externally confirmatory. Numerical source mappings, full-precision tables, saved predictions, matching selections and fit artifacts permit reconstruction without rerunning every pipeline. No new classifier is trained to assemble this supplement. The current deliverable is a frozen local reproducibility package; public deposition, third-party validation and human source confirmation remain separate unfinished steps.

## References
'''

prose_word_count=len(re.sub(r'\{\{\w+\}\}','',BODY).split())
for key,value in tables.items():
    BODY=BODY.replace('{{'+key+'}}',value)
assert not re.search(r'\{\{\w+\}\}',BODY), 'Unexpanded table token'
dest=REV/'manuscript/supplement.md';dest.parent.mkdir(exist_ok=True)
dest.write_text(BODY.strip()+'\n',encoding='utf-8')
(OUT/'numeric_source_mapping.json').write_text(json.dumps({'sources':sources,'tables':mapping},indent=2,ensure_ascii=False),encoding='utf-8')
(OUT/'build_manifest.json').write_text(json.dumps({'status':'COMPLETE','table_count':len(tables),'manuscript_words_including_tables':len(BODY.split()),'prose_words_excluding_tables':prose_word_count,'sources':sources,'supplement_sha256':hashlib.sha256(dest.read_bytes()).hexdigest(),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),'training_performed':False,'old_files_modified':False,'numeric_assertions':'PASS'},indent=2),encoding='utf-8')
print(json.dumps({'output':str(dest),'tables':len(tables),'words_including_tables':len(BODY.split())}))

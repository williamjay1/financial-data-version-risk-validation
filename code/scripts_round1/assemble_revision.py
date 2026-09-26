"""Assemble manuscript and regenerate its numeric tables from frozen outputs.

No models are fitted here. --output-dir writes a separate reproduction.
"""
from pathlib import Path
import argparse, json, re, hashlib
import numpy as np
import pandas as pd
REV=Path(__file__).resolve().parents[1]; ROOT=REV.parent
SOURCE=REV/'manuscript'; OUT=SOURCE
BLOCKS=['2016_2017','2018_2019','2020_2021']
def table(title,cols,rows,note=''):
 text=title+'\n\n| '+' | '.join(cols)+' |\n| '+' | '.join(['---']*len(cols))+' |\n'
 text+='\n'.join('| '+' | '.join(str(x) for x in row)+' |' for row in rows)+'\n'
 return text+('\nNote: '+note+'\n' if note else '')
def block(s):return s.replace('_','–')
def pp(x):return f'{100*x:+.3f}'
def entries(s):
 starts=list(re.finditer(r'(?m)^@\w+\{([^,]+),',s));out={}
 for i,m in enumerate(starts):out[m.group(1)]=s[m.start():starts[i+1].start() if i+1<len(starts) else len(s)].strip()
 return out
def build_tables():
 d=pd.read_csv(REV/'results/models/four_cell_differences.csv');ap=d[d.metric.eq('average_precision')]
 metrics=pd.read_csv(REV/'results/models/metrics.csv');tab={}
 tab['TABLE_RELATED']=table('Table 1. Related evaluation problems and the present comparison.',
 ['Study','Evaluation problem already addressed','Specific paired-version experiment'],[
 ['Zavitsanos et al. [-@zavitsanos2021]','Rare misstatements, chronological evaluation and delayed discovery labels','Original/later feature pairing not reported'],
 ['Yang and Zhu [-@yang2026]','Misstatement discovery lag and prediction evaluation','Feature-version four-cell experiment not reported'],
 ['Zhang et al. [-@zhang2026]','Filing-date horizons, accession alignment and narrative bankruptcy signals','Paired original/later facts and source audit not reported'],
 ['Mattos and Shasha [-@mattos2024]','Low-quality information and recovery/failure after reorganization','Matched accession-version evaluation not reported'],
 ['Kozodoi et al. [-@kozodoi2025]','Selective credit labels and independent validation outcomes','Different outcome and selection mechanism'],
 ['Present study','Financial feature-version choice in a fixed registry-linked cohort','Coherent bundles, four cells, source checks and influence diagnostics']],
 '“Not reported” concerns the specific experiment in the examined text, not an inference that a study ignored timing or data quality. This is a targeted comparison, not a systematic review.')
 sm=json.loads((ROOT/'results/models_20260921T093517075175Z_manifest.json').read_text(encoding='utf-8'))['split_manifest']
 tab['TABLE_SPLITS']=table('Table 2. Original temporal development and test samples.',
 ['Test block','Tuning N / +','Validation year: N / +','Final refit N / +','Test N / +'],
 [[block(s['block']),f"{s['counts']['tuning_train']['n']} / {s['counts']['tuning_train']['positive_windows']}",f"{s['validation_year']}: {s['counts']['validation']['n']} / {s['counts']['validation']['positive_windows']}",f"{s['counts']['refit']['n']} / {s['counts']['refit']['positive_windows']}",f"{s['counts']['test']['n']} / {s['counts']['test']['positive_windows']}"] for s in sm],
 'N counts unweighted filing windows; + counts positive windows. A and B share these rows. The earliest original tuning result is exploratory. Multiple windows from a sampled cluster remain dependent.')
 cov=[]
 for e,label in [('diagnostic_size','Assets only'),('diagnostic_missing','Missingness only'),('diagnostic_size_missing_lag','Assets + missingness + delay'),('fixed_full','Full financial model')]:
  z=metrics[(metrics.experiment==e)&(metrics.model=='LGBM')&(metrics.train_version=='A')&(metrics.score_version=='A')]
  cov.append([label]+[f'{100*z[z.block==b].average_precision.iloc[0]:.3f}' for b in BLOCKS])
 cov.insert(0,['Weighted event prevalence']+[f'{100*metrics[(metrics.experiment=="fixed_full")&(metrics.block==b)].weighted_prevalence.iloc[0]:.3f}' for b in BLOCKS])
 tab['TABLE_COVERAGE']=table('Table 3. Coverage-related baselines using A inputs.', ['Input set / reference']+[block(b) for b in BLOCKS],cov,'Entries are AP percentages, except the prevalence reference. Every fitted row uses the same fixed LightGBM configuration and temporal development rule. The full model includes report delay and missingness.')
 tab['TABLE_SOURCE']=table('Table 4. Source mechanisms kept distinct in the audit.',
 ['Source context','Display-level finding','Analytical treatment'],[
 ['Random sample: 24 landmarks','Assets match in both arms; 23 secondary contexts match, one unresolved','Report sampled denominator; preserve unknown'],
 ['Nobilis: FY2014 and FY2015 in its 2016 filing','API dollar amounts differ by a factor of 1,000 from 22 displayed contexts','Correct only the exact 22 contexts'],
 ['Four purposive sign contexts','Signs differ for operating cash, net income or retained earnings','Four exact-context corrections'],
 ['RCS: comparative assets','Common-control consolidation recast supported by report','Retain scope change; do not relabel as extraction error'],
 ['CIK 0001632970: FY2020 comparative','Reverse acquisition changes accounting predecessor','Retain and qualify economic comparability']],
 'The 26 corrections are display-supported, not original-XBRL-certified. Purposive counts do not estimate prevalence. Exact URLs, periods, units, amounts and locators accompany the audit records.')
 z=ap[ap.experiment.eq('original_four_cell')].sort_values(['block','model'])
 tab['TABLE_FOURCELL']=table('Table 5. The original tuned four-cell AP matrix.',
 ['Block','Model','AA (%)','AB (%)','BA (%)','BB (%)','BB − AA (pp)'],
 [[block(r.block),r.model]+[f'{100*getattr(r,c):.3f}' for c in ['AA','AB','BA','BB']]+[pp(r.total_refit_difference)] for r in z.itertuples()],
 'First letter identifies the fitted pipeline; second identifies scoring inputs. All four cells share test identities and weights. The pipeline includes training-derived preprocessing and validation selection.')
 coverage=pd.read_csv(REV/'results/version_caps/cap_coverage.csv');rows=[]
 for h in [90,365,730]:
  c=coverage[coverage.cap_days.eq(h)].iloc[0]
  m=pd.read_csv(REV/f'results/cap_models/{h}/four_cell_differences.csv');m=m[m.metric.eq('average_precision')&m.model.eq('LGBM')]
  rows.append([str(h),f'{c.available_weighted_percent:.2f}',f'{c.raw_changed_weighted_percent:.2f}']+[pp(m[m.block==b].total_refit_difference.iloc[0]) for b in BLOCKS])
 df=pd.read_parquet(ROOT/'datasets/model_cohort.parquet');w=df.sample_weight
 later=df.later_accession.fillna('').ne('');changed=df.n_coherent_changed.gt(0)
 rows.append(['Latest',f'{100*w[later].sum()/w.sum():.2f}',f'{100*w[changed].sum()/w.sum():.2f}']+[pp(ap[(ap.experiment=='fixed_full')&(ap.model=='LGBM')&(ap.block==b)].total_refit_difference.iloc[0]) for b in BLOCKS])
 tab['TABLE_HORIZONS']=table('Table 6. Later-source availability and fixed LightGBM contrasts.',
 ['Horizon (days)','Bundle available (%)','Raw change (%)','ΔAP 2016–17','ΔAP 2018–19','ΔAP 2020–21'],rows,
 'Availability and change percentages use weighted mass of all 5,502 landmarks. AP contrasts are percentage points, BB minus the common fixed AA anchor. “Latest” uses the retrieval cutoff. These are post-origin retrospective versions.')
 u=pd.read_csv(REV/'results/uncertainty/full_pipeline_distribution_summary.csv');u=u[u.metric.eq('average_precision')].sort_values(['block','model'])
 old=pd.read_csv(ROOT/'results/uncertainty_20260921T093555450801Z_summary.csv');rows=[]
 assert len(u)==6 and (u.valid_replicates==200).all()
 for r in u.itertuples():
  o=old[(old.metric=='average_precision')&(old.model==r.model)&(old.block==r.block)].iloc[0]
  rows.append([block(r.block),r.model,pp(r.original_difference_B_minus_A),f'[{100*o.ci95_low:.3f}, {100*o.ci95_high:.3f}]',pp(r.q50_0),f'[{100*r.q5_0:.3f}, {100*r.q95_0:.3f}]',f'{100*r.positive_fraction_valid:.1f}'])
 tab['TABLE_REFITTING']=table('Table 7. Conditional intervals and complete-pipeline perturbations.',
 ['Block','Model','Original ΔAP','Conditional 95% CI','Refit median','Refit 5–95%','Positive (%)'],rows,
 'All AP quantities are percentage points. The original CI fixes fitted pipelines and certainty cases; the refitting columns summarize 200 paired complete-pipeline weight perturbations. The latter ranges are empirical quantiles, not confidence limits.')
 tab['REFITTING_INTERPRETATION']='All 200 perturbations are valid, comprising 12,000 candidate and final fits. LightGBM has positive AP differences in only 50%, 60% and 60% of replicates; medians are −0.027, +2.047 and +1.046 points. Its empirical 5th–95th percentile ranges extend across zero in every block. A and B select different LightGBM candidates in 45.0%, 67.5% and 58.5% of replicates. This combination indicates substantial development sensitivity despite the original positive point contrasts. Logistic differences are generally smaller in magnitude, but their direction also varies. The original conditional interval for the final-block LightGBM contrast is positive; that narrower conditional result should not be substituted for the full-pipeline diagnostic.'
 return tab

def appendices():
 old=(ROOT/'manuscript/manuscript.md').read_text(encoding='utf-8')
 a=old[old.index('# Appendix A.'):old.index('# References')]
 t=pd.read_csv(REV/'results/models/transition_records.csv',dtype={'cik':str}).fillna('')
 rows=[]
 for rid,g in t.groupby('row_id',sort=False):
  r=g.iloc[0];members=[]
  for k,name in [('in_original_tuning_train','T'),('in_original_validation','V'),('in_original_refit','F'),('in_original_test','E')]:
   b=[str(BLOCKS.index(q.block)+1) for q in g.itertuples() if getattr(q,k)]
   if b:members.append(name+','.join(b))
  missing=len([x for x in str(r.missing_features).split(';') if x])
  rows.append([str(r.cik).zfill(10),str(r.decision_date)[:10],int(r.registry_event_365),missing,int(r.n_changed_A_B),'; '.join(members)])
 a+='\n# Appendix C. Transition landmarks\n\n'+table('Table C1. All transition-report landmarks in the frozen cohort.',
 ['CIK','Origin','Event','Missing','Changed','Original stage membership'],rows,
 'Missing and changed count numerical model features, before missingness flags. T denotes tuning training, V validation, F final refitting and E test evaluation. Numbers 1, 2 and 3 denote chronological blocks. Full accessions, missing-feature names, version differences and stage membership are supplied in the row-level file.')
 a+='\n# Appendix D. Source-verification record and correction rules\n\n'
 a+='The probability audit fixes 12 strata before source reading: three test blocks by recorded event status by any raw component change. Two landmarks are sampled in each stratum. Stratum denominators, inclusion probabilities and the selected rows are retained. The 48 requested fact contexts generate 96 source-arm checks; the six purposive landmarks add 24 source-arm checks. The 54 distinct filing URLs are fewer than the 120 checks because sources and contexts can be reused. Original XBRL context authentication is unknown for all 120 checks. These counts describe the requested sample, not every component used by each model.\n\n'
 a+='The correction key contains CIK, accession, concept, unit, start date when relevant, end date and the exact API value. A correction is applied only when the key matches and the displayed value is directly supported. All ratios are then recomputed from their component values; they are not edited independently. The final correction table contains 22 Nobilis contexts from two fiscal periods plus four sign contexts. It changes 34 version-component cells across A, B and the descriptive per-tag alternative, yielding 14 numerical feature cells across six landmark rows. Of these feature cells, three belong to A, three to B and eight to the descriptive alternative; the latter is not used as an evaluation arm. Initial masks, row identities, outcomes and weights are unchanged. The earlier 15-context revision is preserved as superseded provenance and is not the final corrected experiment.\n\n'
 a+='A second candidate discrepancy at Applied Biosciences remains unresolved: the original displayed operating-income label does not directly certify the inferred subtotal. It is excluded from the correction table. A small liabilities difference that appears in the displayed source itself is also left unchanged. These decisions prevent inferred accounting identities or preferences for internal consistency from being represented as verified corrections.\n\n'
 a+='In the Nobilis context, parent-attributable net income and equity are matched to the selected concepts, rather than substituted with consolidated amounts that include noncontrolling interests [@nobilis2016_10k; @nobilis2017_10k]. In the RCS context, the later comparative assets reflect a common-control transaction and retrospective scope [@rcs2014_10k; @rcs2015_10ka]. The reverse-acquisition example at CIK 0001632970 similarly distinguishes the legal acquirer from the accounting predecessor; its precise accession, note locator and retrieved-source checksum are in the audit ledger.\n\n'
 a+='# Appendix E. Additional AP comparisons\n\n'
 rows=[]
 specs=[('Nominal size ≥ $100m',REV/'results/models/four_cell_differences.csv','size100m_fixed'),('CPI size proxy',REV/'results/cpi_domain/four_cell_differences.csv',None),('Source corrected, tuned',REV/'results/corrected_models_v2/four_cell_differences.csv','source_corrected_tuned'),('Source corrected, fixed',REV/'results/corrected_models_v2/four_cell_differences.csv','source_corrected_fixed')]
 for label,path,e in specs:
  d=pd.read_csv(path);d=d[d.metric.eq('average_precision')]
  if e is not None:d=d[d.experiment.eq(e)]
  assert len(d)==6,(label,len(d),d.experiment.unique())
  for model in ['LR','LGBM']:
   z=d[d.model.eq(model)];rows.append([label,model]+[pp(z[z.block==b].total_refit_difference.iloc[0]) for b in BLOCKS])
 a+=table('Table E1. Domain and final source-correction contrasts.', ['Analysis','Model']+[block(b) for b in BLOCKS],rows,'Entries are BB minus AA AP in percentage points. Domain restrictions apply to development and test rows using original A assets; source corrections retain the full cohort. Final corrections use all 26 verified contexts. All comparisons were added during revision.')
 a+='\nThe full outputs also retain every cross-scoring cell, calibration diagnostic and finite-horizon comparison for logistic regression. They are provided as machine-readable tables rather than selecting a preferred subset of favorable specifications. Models and pipelines vary across rows, so these contrasts must not be treated as independent replications.\n'
 return a

def main(output_dir=None):
 out=Path(output_dir) if output_dir else OUT;out.mkdir(parents=True,exist_ok=True)
 tabs=build_tables();text='\n\n'.join((SOURCE/f).read_text(encoding='utf-8') for f in ['front.md','methods.md','results.md','discussion.md'])
 for key,value in tabs.items():text=text.replace('{{'+key+'}}',value)
 text+='\n\n'+appendices()+'\n\n# References\n\n::: {#refs}\n:::\n'
 if re.search(r'\{\{[A-Z_]+\}\}',text):raise ValueError('Unresolved token')
 bib=entries((ROOT/'manuscript/references.bib').read_text(encoding='utf-8'))
 bib.update(entries((REV/'literature/bibliography_updates.bib').read_text(encoding='utf-8')))
 bib['bls_cpi']='''@misc{bls_cpi,
 author = {{U.S. Bureau of Labor Statistics}},
 title = {Consumer Price Index for All Urban Consumers: U.S. city average, all items, not seasonally adjusted (CUUR0000SA0)},
 year = {2026}, url = {https://www.bls.gov/cpi/}, urldate = {2026-09-22},
 note = {Official public API observations; 1980 annual average and 2009--2021 monthly values. Current historical series, not historical retrieval vintages}
}'''
 cited=set(re.findall(r'(?<!\w)@([A-Za-z0-9_]+)',text));missing=cited-set(bib)
 if missing:raise ValueError('Unknown references '+str(missing))
 (out/'manuscript.md').write_text(text,encoding='utf-8')
 (out/'references.bib').write_text('\n\n'.join(v for k,v in bib.items() if k in cited)+'\n',encoding='utf-8')
 (out/'generated_tables.json').write_text(json.dumps(tabs,indent=2,ensure_ascii=False),encoding='utf-8')
 summary={'status':'assembled','words':len(re.findall(r"\b[\w'-]+\b",text)),'cited_references':len(cited),'source':'frozen model and audit outputs','tables':len(re.findall(r'^Table [A-Z0-9]',text,re.M)),'figures':len(re.findall(r'^Figure \d',text,re.M)),'sha256':hashlib.sha256((out/'manuscript.md').read_bytes()).hexdigest(),'normalized_text_sha256':hashlib.sha256(text.encode()).hexdigest()}
 (out/'content_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8');print(json.dumps(summary))
 return out/'manuscript.md'

if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--output-dir');main(p.parse_args().output_dir)

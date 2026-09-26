"""Assemble the research text and tables from frozen, identified result files."""
from pathlib import Path
import json,re
import numpy as np
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]; MAN=ROOT/'manuscript'; RES=ROOT/'results'
MAIN='models_20260921T093517075175Z'
CI='uncertainty_20260921T093555450801Z'
FCI='uncertainty_20260921T093555459899Z'
S1='sensitivity_source_scale_corrected/models_20260921T093617431021Z'
S2='sensitivity_no_transition/models_20260921T093617432022Z'

def table(headers,rows):
    return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])+'\n'
def block(s):return s[:4]+'–'+s[-2:]
def interval(row):return f"[{100*row.ci95_low:.3f}, {100*row.ci95_high:.3f}]"
def fig(path,caption):return f'\n![]({path.as_posix()}){{width=6.6in}}\n\n{caption}\n'

def main():
    mm=json.loads((RES/(MAIN+'_manifest.json')).read_text(encoding='utf-8'))
    assert mm['status']=='completed' and mm['main_fits_completed']==12
    cs=json.loads((RES/'cohort_summary.json').read_text(encoding='utf-8'))
    assert cs['status']=='FINAL_COHORT_FROZEN' and cs['cohort_sha256']==mm['input_sha256']
    met=pd.read_csv(RES/(MAIN+'_metrics.csv'))
    ci=pd.read_csv(RES/(CI+'_summary.csv')); fci=pd.read_csv(RES/(FCI+'_summary.csv'))
    sens1=pd.read_csv(RES/(S1+'_paired_differences.csv'))
    sens2=pd.read_csv(RES/(S2+'_paired_differences.csv'))
    assert ci.valid_boot.eq(1000).all() and fci.valid_boot.eq(1000).all()
    figures=sorted((RES/'figures').glob(MAIN+'_figures_*'))[-1]
    desc=figures.name
    feat=pd.read_csv(RES/('descriptive_'+desc+'_feature_changes.csv'))
    cohort=pd.read_parquet(ROOT/'datasets/model_cohort.parquet')
    front=(MAN/'front_methods.md').read_text(encoding='utf-8')
    front=front.replace('Supplementary Table S1','Appendix A').replace('Supplementary Table S2','Table 2')
    # Counts remain in the main text; no external supplement is needed to assess
    # the few-event development folds.
    title='Financial statement vintage choice in registry-linked bankruptcy prediction'
    abstract='''Financial statement values retrieved today can differ from those associated with the original filing accession. We examine how this version choice affects rare-event bankruptcy prediction without changing the paired observation set or initial missingness. A historical annual-filing frame supports probability sampling of cofiling clusters and direct linkage to first Bankruptcy Research Database events. The eligible sample contains 5,502 filing windows from 990 company identifiers, including 188 event windows. The earliest tuning and validation samples contain only three and seven event windows. Original-accession and coherent later-accession inputs are evaluated with regularized logistic regression and LightGBM across three chronological test blocks. Later bundles change at least one raw component in 23.8% of observed windows. Refit LightGBM average precision increases by 2.84, 2.77, and 1.77 percentage points, while Brier scores worsen. Holding the original fitted model fixed instead yields average-precision changes of −2.78, +1.37, and +0.11 points. Conditional sampling-design intervals do not account for model-training or rare-case composition uncertainty. Excluding 12 transition-report windows reverses the final block's refit LightGBM contrast to −3.90 points. Source checks distinguish a thousandfold API scale discrepancy from a common-control accounting recast; correcting the verified scale leaves LightGBM's principal contrasts unchanged. These results support treating financial version rules as part of the evaluation specification, but do not establish a uniform direction of hindsight bias or a deployable performance gain. The outcome is a directly linked registry event, and the original-accession values are reconstructions from the current API rather than authenticated historical API snapshots.'''
    assert len(abstract.split())<=250
    text=f'---\ntitle: "{title}"\nlang: en-US\n---\n\n# Abstract\n\n{abstract}\n\n**Keywords:** Bankruptcy prediction; Financial statement versions; Rare events; Evaluation sensitivity; SEC XBRL; Probability sampling\n\n'+front
    text+='''
# 4 Results

## 4.1 Eligible domain and event information

The historical metadata cover all 48 quarters of 2010–2021. The 48 annual form-count comparisons, covering four annual-report form categories over 12 years, exactly match the external count archive. All 1,780 official company–accession records inspected for 162 previously available CIKs also match on identifier, date, and form. The latter is a convenience-source cross-check, not a random validation sample of the complete archive.

For the 1,518 selected CIKs, collection resolves 3,347 required primary and historical-file requests: 3,032 return data and 315 return no record. The final domain contains 5,502 annual-filing windows from 990 CIKs in 973 observed cofiling clusters. It includes 188 positive windows, each linked to a different first-event CIK. These are identifier-linked events, not a verified count of independent legal corporate-group failures. Eligible CIKs comprise 250 of 438 selected certainty-stratum CIKs and 740 of 1,080 probability-sampled CIKs. The 528 selected identifiers with no eligible window remain excluded by the documented data and timing rules, rather than replaced.

Table 1 shows the sequential observation flow. In particular, requiring an original-accession asset value removes 1,924 otherwise eligible pre-event windows. The sample's inclusion probabilities therefore support inference only within the accessible standard-tag domain. The weighted sum is 63,397.604 filing landmarks; it is a design-weighted domain estimate, not the number of records directly observed. Annual coverage varies markedly: only 48 eligible windows occur in 2010, compared with 628 in 2012 (Figure 1).

Table 1. Formation of the eligible paired cohort.

'''
    flow=pd.read_csv(RES/'cohort_flow.csv')
    labels=['Parsed filings with accessible companyfacts','Prediction origin in 2010–2021','Matched to historical frame','Before first directly linked event','Positive original-accession assets','Nonnegative reporting delay']
    text+=table(['Sequential inclusion rule','Windows','CIKs','Positive windows'],[[labels[i],f'{r.rows:,}',f'{r.ciks:,}',int(r.positive_windows)] for i,r in enumerate(flow.itertuples())])
    text+='\nNote: Counts are unweighted and sequential. The first row precedes the observation-domain restrictions; all final A/B comparisons use the same 5,502 rows.\n'
    text+=fig(figures/'figure1_annual_sample.png','Figure 1. Eligible observations and registry-event windows by prediction-origin year. Panel A reports design-weighted landmarks; Panel B reports unweighted positive windows and distinct positive CIKs, which coincide in this sample. Neither panel establishes coverage of all legal bankruptcies.')
    text+='''
The three test blocks contain 51, 28, and 44 positive windows, respectively (Table 2). The final refit samples contain 39, 95, and 124 positives. The earliest tuning sample, however, has only three positives, and its validation year has seven. This is a substantive weakness of that block's model selection. Its scores are reported, but they cannot establish stable hyperparameter selection in a rare-event problem. The later blocks provide more development events, without eliminating finite-case or temporal uncertainty.

Table 2. Chronological development and evaluation samples.

'''
    rows=[]
    for split in mm['split_manifest']:
        c=split['counts']; t=c['test']
        rows.append([block(split['block'])]+[f"{c[k]['n']:,} ({c[k]['positive_windows']})" for k in ['tuning_train','validation','refit','test']]+[f"{100*t['weighted_positive_windows']/t['weighted_n']:.3f}%"])
    text+=table(['Test block','Tuning train','Validation','Final refit','Test','Weighted event rate'],rows)
    text+='\nNote: Entries are windows (positive windows). In these samples each positive window corresponds to a distinct first-event CIK. Validation years are 2013, 2015, and 2017. Training requires a completed 365-day horizon plus the assumed 90-day administrative buffer.\n'
    text+='''
## 4.2 Frequency and meaning of version differences

A coherent later-accession bundle is available for 4,128 windows (75.0% unweighted; 75.5% weighted). For the remaining windows, B retains A. At least one raw accounting component changes in 1,307 windows (23.8% unweighted; 21.9% weighted). Among available later bundles, the median filing-date gap is 364 days. These later representations predominantly occur around another annual reporting cycle; they are not contemporaneous alternatives that could all have been used at the original prediction origin.

Changes in model inputs have different denominators from changes in raw components. Conditional on initial observability of each input, the weighted proportion changed ranges from 9.7% for log assets to 15.5% for operating income divided by assets (Figure 2). Revenue and operating cash flow ratios change in 14.1% and 14.2%, respectively. Identical missingness across A and B prevents these comparisons from being driven by a later version simply filling initially absent variables. It does not remove restrictions caused by unavailable standard tags in both versions.

The descriptive per-concept construction C changes a raw component in 2,245 windows. It combines more than one source accession in 5,115 windows, or 93.0% of weighted landmarks. Mixing sources does not necessarily change every number, but it obscures which filing supports the complete vector. Two C reconstructions also have a zero asset denominator where A and B have positive assets. C is consequently retained as a source-lineage diagnostic and is not used in the prediction comparison or the paired-input figure.
'''
    text+=fig(figures/'figure2_input_changes.png','Figure 2. Input differences between coherent later and original-accession reconstructions. Bars show the design-weighted percentage changed among observations with a finite A value of that input. Change requires an absolute difference greater than 10⁻¹² times the maximum of one and the two absolute values. A and B have identical missingness; denominators are reported in Appendix A.')
    examples=(MAN/'source_examples.md').read_text(encoding='utf-8').replace('# Source examples','### Source-level interpretation')
    text+='\n'+examples+'\n'
    text+='''
## 4.3 Paired model evaluation

All 48 prespecified candidate fits and 12 final main-analysis fits complete. Table 3 reports the primary average-precision comparison. Refit LightGBM AP rises from 0.2475 to 0.2759 in 2016–2017, from 0.1556 to 0.1833 in 2018–2019, and from 0.0739 to 0.0916 in 2020–2021. The corresponding changes are +2.839, +2.768, and +1.766 percentage points. Logistic regression changes are much smaller and negative in all three main comparisons. These are comparisons between the two specified learners on a fixed accounting input set, not a ranking of all available bankruptcy prediction methods.

Table 3. Sampling-weighted average precision under separately refitted versions.

'''
    ap=ci.loc[ci.metric.eq('average_precision')].sort_values(['block','model'],ascending=[True,False])
    text+=table(['Test block','Learner','AP: A','AP: B','ΔAP (pp)','Conditional 95% interval (pp)'],[[block(r.block),r.model,f'{r.A:.4f}',f'{r.B:.4f}',f'{100*r.difference_B_minus_A:+.3f}',interval(r)] for r in ap.itertuples()])
    text+='''
Note: AP is on a zero-to-one scale; differences and intervals are percentage points (pp). The 1,000 paired rescaled cluster replicates hold fitted models and certainty-stratum cases fixed. Intervals are approximate, pointwise sampling-design intervals, not simultaneous or full generalization intervals.

The LightGBM AP intervals include zero in the first two blocks. The final block's conditional interval is positive, but it excludes training variability and case-composition uncertainty and does not establish robustness to the prespecified transition-report sensitivity below. No pooled significance claim is made across the blocks.

Ranking and probability quality diverge. LightGBM's Brier score worsens under B in all three main comparisons: 0.003819 to 0.003916, 0.003763 to 0.004005, and 0.007117 to 0.008345. In the last two blocks, both versions have worse Brier scores than the constant prevalence reference, despite substantially better AP. LightGBM's estimated calibration slopes range from 0.353 to 0.539 across arms and blocks. These diagnostics caution against interpreting the high ranking scores as calibrated bankruptcy probabilities. Complete main metrics, including unfavorable results, appear in Appendix B.

The frozen-A diagnostic changes the interpretation further (Table 4; Figure 3). In 2016–2017, replacing only the test inputs lowers LightGBM AP by 2.777 points, whereas refitting the later-data pipeline raises it by 2.839 points. The corresponding frozen changes in the later blocks are +1.367 and +0.112 points. The disagreement establishes that the refit contrast cannot be attributed solely to the immediate effect of substituting test inputs. It combines numerical changes in training, preprocessing, candidate selection, and evaluation. This comparison does not separately identify the contribution of each stage.

Table 4. Average-precision sensitivity with the A model and preprocessing held fixed.

'''
    fp=fci.loc[fci.metric.eq('average_precision')].sort_values(['block','model'],ascending=[True,False])
    text+=table(['Test block','Learner','AP: A inputs','AP: B inputs','ΔAP (pp)','Conditional 95% interval (pp)'],[[block(r.block),r.model,f'{r.A:.4f}',f'{r.B:.4f}',f'{100*r.difference_B_minus_A:+.3f}',interval(r)] for r in fp.itertuples()])
    text+='\nNote: No additional models are fitted. The interval interpretation is the same as Table 3.\n'
    text+=fig(figures/'figure3_paired_average_precision.png','Figure 3. Paired average-precision contrasts under refitting and fixed-model input replacement. Points are B minus A, in percentage points; bars are approximate conditional pointwise 95% sampling-design intervals. The common horizontal scale allows comparison of the two diagnostics. Intervals do not include training, tuning, registry omission, or rare-case composition uncertainty.')
    text+='''
## 4.4 Prespecified sensitivity analyses

The source-supported Nobilis correction changes only two original-filing landmarks across the paired versions: log assets changes where the audited accession supplies the amount, while same-bundle ratios retain their original values. The correction leaves all three LightGBM AP contrasts unchanged at reported precision, and logistic contrasts change only slightly (Table 5). This particular scale anomaly therefore does not explain the main LightGBM pattern. It does not establish that no other source-level anomalies matter.

Excluding the 12 transition-report windows removes one positive and leaves 5,490 observations. This restriction is more consequential. The final-block LightGBM contrast reverses from +1.766 to −3.898 points; its five-percent recall contrast also reverses, from +11.36 to −11.36 points. The earlier AP contrasts remain positive, but the reversal rules out a claim that later versions consistently improve evaluation under the tested settings. Because transition exclusion is applied to development and evaluation samples, it changes the fitted pipeline and its target domain. The contrast cannot be interpreted as the effect of deleting 12 test observations or as evidence that transition reports cause the original gain.

Table 5. Refit AP differences under both specified sensitivity analyses.

'''
    rows=[]
    for r in ap.itertuples():
        one=sens1.loc[sens1.block.eq(r.block)&sens1.model.eq(r.model)].iloc[0]
        two=sens2.loc[sens2.block.eq(r.block)&sens2.model.eq(r.model)].iloc[0]
        rows.append([block(r.block),r.model,f'{100*r.difference_B_minus_A:+.3f}',f'{100*one.average_precision_difference:+.3f}',f'{100*two.average_precision_difference:+.3f}'])
    text+=table(['Test block','Learner','Main (pp)','Verified scale correction (pp)','Exclude transitions (pp)'],rows)
    text+='''
Note: Entries are B minus A in percentage points. Each sensitivity repeats the same candidate grids and temporal rules, with 48 candidate fits and 12 final fits. The scale correction preserves the cohort; transition exclusion changes the eligible domain. These are sensitivity estimates, not additional independent replications or a search for a preferred specification.

# 5 Discussion

## 5.1 What version-aware evaluation adds

The results identify a reproducibility problem at the junction between accounting representation and model evaluation. A year and a financial concept do not uniquely identify the number supplied to a learner. Accession, reporting perimeter, recorded unit, and extraction scale can also matter. The contribution is a matched evaluation procedure that preserves initial observability, reports the sampling design, and distinguishes refitting from direct input replacement. It makes a particular source of disagreement observable without asserting that every disagreement is an accounting error.

This distinction refines the broader concern with low-quality financial information. Missingness, rejection of unreliable predictions, and incomplete credit labels have already received methodological attention [@mattos2024; @bargagli2024; @kozodoi2025]. The present evidence concerns a different choice among nonmissing amounts tied to the same historical period. Likewise, label discovery delay and historical feature selection are related timing problems but require separate controls [@yang2026]. A chronological test block addresses the ordering of observations; it does not certify the historical availability of every feature value within an observation. This is consistent with the broader warning that evaluation leakage can survive superficially plausible train–test divisions [@kapoor2023].

The empirical answer is conditional. Refit AP increases for LightGBM in the main design, yet its probability error worsens, the fixed-model comparison sometimes points in the opposite direction, and transition exclusion reverses the final-block AP contrast. Logistic AP is comparatively insensitive in the principal specification, although its capacity recall and selected regularization can change. Taken together, these findings support reporting version rules and the full fitting procedure as part of the experimental specification. They do not support a universal correction factor for published bankruptcy scores, a claim that later disclosures always create optimistic bias, or a claim that one learner is intrinsically more reliable under all accounting revisions.

## 5.2 Implications for data construction and financial model use

The source examples show why audit priorities cannot be set from the size of a numerical discrepancy alone. A uniform thousandfold monetary scaling error can cancel in ratios while remaining in log size. A common-control recast can preserve the concept name, unit, and period while changing the economic scope of the comparator. Source coherence is therefore useful but insufficient for semantic equivalence. Financial data work requires both reproducible selection rules and targeted reading of the underlying statements.

For retrospective research, an accession-based comparison offers a practical diagnostic when historical API snapshots have not been archived. Its outputs should remain labeled as reconstructions. For prospective systems, preserving the actual retrieved feature snapshot at each forecast origin would provide stronger evidence of availability than reconstruction after the outcome is known. A later comparative bundle can be informative for measurement research, but its superior retrospective ranking, where observed, cannot justify its use as an attainable historical trading or credit-screening performance estimate.

The separation between AP and Brier score also matters for application claims. Ranking cases higher in a fixed retrospective block can coexist with overly extreme probabilities and worse mean squared probability error. A system intended to set credit limits, price risk, or allocate capital would require validation of probability quality and a decision rule aligned with information arrival. This study demonstrates neither such an operational policy nor profitability. Its five-percent capacity measure is a retrospective comparison of filing windows, and the underlying registry label remains narrower than all forms of corporate distress.

## 5.3 Scope and remaining uncertainty

Several boundaries determine what can be inferred. First, the BRD target covers directly linked first events under the registry's inclusion rules. Absent events, identifiers attached to other entities, small private failures, and unrecorded proceedings can remain outside that target. Inverse inclusion weights correct the explicit probability sampling of other cofiling clusters; they do not correct unknown registry omissions or authenticate healthy controls.

Second, original-asset observability restricts the analyzed population. Early coverage is particularly sparse, custom tags can be absent from the selected standard-concept hierarchy, and economically different concepts may occupy analogous feature slots across companies. Version matching holds the selected concept fixed within a pair, but does not solve cross-company measurement equivalence. The two source examples are purposively examined explanations, not a prevalence estimate of all accounting or extraction errors. Current companyfacts data may themselves have changed since the original filing.

Third, the earliest development fold contains too few positives to support a strong claim about model-selection stability. The later folds also contain modest event counts. The paired bootstrap quantifies only the stated sampling-design component while fixing models and observed cases. It cannot be used as a complete interval for performance in a new period, with newly sampled failures, or after retraining. Sensitivity to exclusion of a small transition-report subset reinforces this limitation rather than resolving it.

Finally, the experiment is deliberately confined to a documented accounting feature set and two established learners. It does not test all contemporary predictors or architectures. A fuller predictive benchmark would need appropriate market and text variables, comparable access timing, and competitive task-specific methods. That is a separate question from whether a specified numerical version rule changes the evaluation of an otherwise matched procedure. The present design supports the latter question at the reported scope.

# 6 Conclusion

Financial version choice changes both the numbers in a historical predictor table and, in some settings, the conclusions drawn from model evaluation. In this registry-linked study, coherent later inputs affect refit ranking differently from fixed-model scoring, while probability error and transition-report sensitivity constrain favorable interpretations. A reproducible evaluation should identify the financial accession rule, preserve the original missingness pattern, distinguish source scale from accounting scope, and report results that contradict a simple improvement narrative. The evidence establishes sensitivity within the accessible standard-tag registry domain; it does not establish a universal hindsight-bias direction or deployable performance gain.

# Data and code availability

An accompanying reproducibility package contains the derived paired cohort, financial fact lineage, sampling frame, analysis code, selected hyperparameters, fitted preprocessing, held-out predictions, interval outputs, and figure data. The original SEC, BRD, and historical-index sources are identified in the references and source manifests. Original downloads are preserved separately, and no unrestricted redistribution license for third-party source archives is asserted. No public repository accession has been assigned to this local package.

# Use of generative AI

OpenAI Codex assisted literature retrieval, research design, programming, analysis, visualization, and manuscript preparation. Checks included comparison with documented primary sources, deterministic data identities, reconstruction of stored predictions, and numerical audits. The extent of source-level accounting verification is stated in the text; automated agreement with an API record does not constitute independent verification of every financial statement. No synthetic observations were used as empirical evidence. Human authors remain responsible for reviewing and approving any submitted version.

# Appendix A. Accounting inputs and observed denominators

All selected monetary facts use the retrieved USD unit and the same concept within each A/B pair. Assets, liabilities, equity, cash, current assets, current liabilities, and retained earnings are instant facts. Net income, revenue, operating income, and operating cash flow require a 330–400-day period. The hierarchy below is evaluated in order; conflicting contexts within the chosen candidate are treated as ambiguous by the extraction rule.

'''
    tags=json.loads((RES/'vintage_panel_build_summary.json').read_text())['tag_mapping']
    names={'assets':'Assets','liabilities':'Liabilities','equity':'Equity','cash':'Cash','current_assets':'Current assets','current_liabilities':'Current liabilities','net_income':'Net income','revenue':'Revenue','operating_income':'Operating income','operating_cash':'Operating cash flow','retained_earnings':'Retained earnings'}
    for key,value in tags.items():text+='- **'+names[key]+'**: '+ '; then '.join('`'+v+'`' for v in value)+'.\n'
    text+='''
The ten model inputs are natural log assets; eight raw components divided by assets (liabilities, equity, cash, net income, revenue, operating income, operating cash flow, and retained earnings); and current assets minus current liabilities, divided by assets. Reporting lag, in days from fiscal end to original filing, is shared across versions. Each of these eleven predictors has a missingness indicator. All fit-dependent preprocessing is learned inside the relevant training partition.

Table A1. Initial observability and paired input changes.

'''
    text+=table(['Input','A observed, raw N','A observed, weighted N','Changed, weighted %'],[[r.label,f'{r.raw_A_observed:,}',f'{r.weighted_A_observed:,.3f}',f'{100*r.weighted_change_proportion_A_observed:.2f}'] for r in feat.itertuples()])
    text+='\nNote: Weighted N is the sum of inverse inclusion probabilities, not an integer sample count. Percentages use the initially observed denominator for each feature.\n'
    text+='''
# Appendix B. Complete main prediction metrics

Table B1. Discrimination, probability error, screening, and calibration.

'''
    rows=[]
    for r in met.itertuples():
        model='Constant' if r.model=='PREVALENCE' else r.model+' '+r.version
        slope='Not identified' if pd.isna(r.calibration_slope) else f'{r.calibration_slope:.3f}'
        rows.append([block(r.block),model,f'{r.roc_auc:.4f}',f'{r.brier:.6f}',f'{100*r.retrospective_recall_at_5percent:.2f}',f'{r.calibration_intercept:.3f}',slope])
    text+=table(['Block','Learner / arm','ROC area','Brier','Recall 5% (%)','Cal. intercept','Cal. slope'],rows)
    text+='\nNote: Intercept is calibration-in-the-large with logit slope fixed at one. Slope is estimated jointly with a free intercept; the joint intercept is retained in the analysis files. These are held-out diagnostics, not test-set recalibration. The constant reference uses the mature refit sample prevalence.\n'
    text+='''
Table B2. Validation-selected hyperparameters.

'''
    chosen=met.loc[met.model.isin(['LR','LGBM'])]
    rows=[]
    for r in chosen.itertuples():
        params=json.loads(r.selected_parameters)
        desc='C = '+str(params['C']) if r.model=='LR' else f"Leaves = {params['num_leaves']}; minimum leaf N = {params['min_child_samples']}"
        rows.append([block(r.block),r.model,r.version,desc])
    text+=table(['Block','Learner','Arm','Selected parameters'],rows)
    text+='\nNote: Selection maximizes weighted validation AP among the four prespecified candidates. Candidate scores and prediction files are retained in the reproducibility package.\n\n# References\n\n::: {#refs}\n:::\n'
    (MAN/'manuscript.md').write_text(text,encoding='utf-8')
    index={'main_model_manifest':str(RES/(MAIN+'_manifest.json')),
           'model_runs':[{'kind':kind,'manifest':str(RES/(p+'_manifest.json'))} for kind,p in [('main',MAIN),('verified_scale',S1),('exclude_transitions',S2)]],
           'uncertainty_runs':[{'kind':kind,'manifest':str(RES/(p+'_manifest.json'))} for kind,p in [('refit',CI),('frozen_A',FCI)]],
           'figure_directory':str(figures),'cohort_sha256':cs['cohort_sha256'],'manuscript':str(MAN/'manuscript.md')}
    (RES/'final_run_index.json').write_text(json.dumps(index,indent=2),encoding='utf-8')
    report={'abstract_words':len(abstract.split()),'manuscript_words_including_tables':len(text.split()),'tables':len(re.findall(r'^Table [AB]?\d+\.',text,re.M)),'figures':3,'referenced_keys':sorted(set(re.findall(r'@([A-Za-z0-9_]+)',text)))}
    (RES/'manuscript_content_summary.json').write_text(json.dumps(report,indent=2),encoding='utf-8')
    print(json.dumps(report))

if __name__=='__main__':main()

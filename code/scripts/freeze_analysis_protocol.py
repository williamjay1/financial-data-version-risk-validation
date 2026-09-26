"""Record design amendments before the formal paired model comparison."""
import json
import shutil
from datetime import datetime,timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
def main():
    p = ROOT/'phase2_protocol.json'
    previous = ROOT/'results'/'protocol_before_full_cohort.json'
    if not previous.exists():
        shutil.copyfile(p,previous)
    v = json.loads(p.read_text(encoding='utf-8'))
    v['status'] = 'DESIGN_LOCKED_COLLECTION_IN_PROGRESS'
    v['design_lock_utc'] = datetime.now(timezone.utc).isoformat()
    v['not_preregistered'] = True
    v['design_origin'] = 'Developed after exploratory source audits; locked before any formal full-cohort model scores.'
    v['data_gate']['reason'] = 'Historical frame independently checked and cluster probability sample locked; SEC collection, extraction audit and final cohort checks pending.'
    v['data_gate']['training_allowed_now'] = False
    v['primary_comparison']['versions'] = ['A_ORIGINAL_ACCESSION_RECONSTRUCTION','B_LATEST_COHERENT_COMPARATIVE_ACCESSION']
    v['primary_comparison']['version_rule'] = 'B uses one later accession containing all A-observed financial facts with identical concept, USD unit and period boundaries. With no complete later bundle, B=A. C per-tag-latest synthetic hybrids are descriptive sensitivity only.'
    v['primary_comparison']['target'] = '365-day first BRD event directly linked to CikBefore; no inference about all legal bankruptcies or all members of corporate groups.'
    v['primary_comparison']['data_vintage_limit'] = 'Current SEC companyfacts tied to original accessions reconstruct reported-period facts; historical API extraction vintages were not archived. Do not call A an authenticated historical API snapshot.'
    v['primary_comparison']['primary_estimand'] = 'B-minus-A sampling-weighted average precision within each prespecified held-out time block, separately for each diagnostic learner.'
    v['sampling'] = {'unit':'connected components of shared 2010–2021 annual accession numbers','certainty':'every component with any directly BRD-linked CIK through 2022',
                     'noncase_srs_clusters':1000,'noncase_population_clusters':14546,'seed':20260921,
                     'all_members_inherit_cluster_probability':True,'outcomes_propagated_to_cofilers':False,
                     'no_unavailable_XBRL_response_adjustment':'Inference targets the accessible standard-tag positive-assets domain; sampled unavailable CIKs remain in flow tables.'}
    v['domain_rules'] = ['selected sampling-frame CIK','CIK/accession/filed date present in historical master annual frame','decision day 2010-01-01 to 2021-12-31','decision strictly before first directly BRD-linked event','finite positive original-accession Assets','nonnegative reporting delay']
    v['time_blocks'] = [['2016-01-01','2017-12-31'],['2018-01-01','2019-12-31'],['2020-01-01','2021-12-31']]
    v['label_maturity'] = {'horizon_days':365,'additional_buffer_days':90,'rule':'training decision +455 days <= validation/test block start','limitation':'Administrative buffer, not proof of historical registry publication timestamps'}
    v['tuning'] = {'validation_calendar_year':'test-start year minus 3','fit_before_validation':'only observations with complete horizon and buffer before validation year starts',
                   'refit_after_selection':'all training landmarks matured before test start','LR_C':[0.01,0.1,1,10],
                   'LGBM_num_leaves':[7,15],'LGBM_min_child_samples':[30,60],'LGBM_learning_rate':0.05,'LGBM_estimators':300,
                   'criterion':'sampling-weighted validation average precision','weights':'used in preprocessing, fitting and metrics; mean-one normalization allowed within fit'}
    v['preprocessing'] = {'winsorization':'weighted training 1st and 99th percentile','imputation':'weighted training median','indicators':'fixed missingness indicator for each feature','LR_scaling':'weighted training mean and standard deviation','shared_covariate':'report_lag_days','no_class_rebalancing':True}
    v['uncertainty'] = 'Paired rescaled stratified cluster bootstrap with noncase SRS finite-population correction; certainty clusters fixed, all 1000 sampled noncase clusters retained including zero-domain contributors. Conditional on fitted models and observed registry labels; no coverage claim for future crises or model training uncertainty.'
    v['resource_policy']['approved_derived_cache_budget_gib'] = 12
    v['resource_policy']['free_D_gib_at_expansion'] = 159.8
    v['resource_policy']['note'] = 'Pilot 2GiB limit expanded after successful 1.88GB metadata download and 0.48GB case SEC audit; ample D space checked. All model reads and outputs stay on D.'
    p.write_text(json.dumps(v,indent=2,ensure_ascii=False),encoding='utf-8')
    print(v['status'])

if __name__ == '__main__':
    main()

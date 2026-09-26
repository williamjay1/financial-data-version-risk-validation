"""Apply the locked domain rules and sampling weights; do not fit any model."""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA, OUT = ROOT/'datasets', ROOT/'results'

def main():
    panel = pd.read_parquet(DATA/'vintage_panel.parquet')
    frame = pd.read_parquet(DATA/'sampling_frame.parquet')
    selected = frame.loc[frame.selected].copy()
    annual = pd.read_parquet(DATA/'universe_annual_filings_2010_2021.parquet')
    fields = ['cik','cluster_id','sampling_stratum','inclusion_probability','sample_weight']
    p = panel.merge(selected[fields],on='cik',how='inner',validate='many_to_one')
    flow = [{'stage':'selected CIKs with parsed annual filings and accessible facts','rows':len(p),'ciks':p.cik.nunique(),'positive_windows':int(p.registry_event_365.sum())}]
    # The historical frame is the sole origin of eligible landmarks.
    original_keys = set(zip(annual.cik,annual.accession_number,annual.filing_date))
    p['in_historical_frame'] = [(c,a,d) in original_keys for c,a,d in zip(p.cik,p.accession,p.filing_date)]
    rules = [
        ('decision date 2010–2021',p.decision_date.between('2010-01-01','2021-12-31')),
        ('CIK/accession/date exists in historical annual frame',p.in_historical_frame),
        ('strictly before first directly linked registry event',p.pre_first_registry_event),
        ('original-accession positive assets',np.isfinite(p.A_log_assets)),
        ('nonnegative reporting lag',p.report_lag_days.ge(0)),
    ]
    keep = pd.Series(True,index=p.index)
    for label,rule in rules:
        keep &= rule
        q = p.loc[keep]
        flow.append({'stage':label,'rows':len(q),'ciks':q.cik.nunique(),'positive_windows':int(q.registry_event_365.sum())})
    q = p.loc[keep].copy().sort_values(['decision_date','cik','accession']).reset_index(drop=True)
    feats = [c[2:] for c in q if c.startswith('A_')]
    assert len(feats) == 10
    assert not q.duplicated(['cik','fiscal_end']).any()
    assert np.isfinite(q[[f'A_{f}' for f in feats]].to_numpy()).sum() >= len(q)
    # Denominator anomalies must be adjudicated, never silently selected on B.
    mask_a = q[[f'A_{f}' for f in feats]].isna().to_numpy()
    mask_b = q[[f'B_{f}' for f in feats]].isna().to_numpy()
    assert np.array_equal(mask_a,mask_b), 'A/B missingness differs; inspect later denominator/context anomalies before fitting.'
    assert (q.groupby('cluster_id').sample_weight.nunique() == 1).all()
    q.to_parquet(DATA/'model_cohort.parquet',index=False)
    pd.DataFrame(flow).to_csv(OUT/'cohort_flow.csv',index=False)
    q['year'] = pd.to_datetime(q.decision_date).dt.year
    annual_stats = []
    for year,g in q.groupby('year'):
        annual_stats.append({'year':int(year),'rows':len(g),'ciks':g.cik.nunique(),'clusters':g.cluster_id.nunique(),
                             'positive_windows':int(g.registry_event_365.sum()),'distinct_event_ciks':g.loc[g.registry_event_365.eq(1),'cik'].nunique(),
                             'weighted_landmarks':g.sample_weight.sum(),'weighted_event_prevalence':np.average(g.registry_event_365,weights=g.sample_weight),
                             'kish_landmark_effective_n':g.sample_weight.sum()**2/(g.sample_weight**2).sum(),
                             'coherent_later_available':int(g.later_accession.ne('').sum()),'coherent_changed_rows':int(g.n_coherent_changed.gt(0).sum()),
                             'hybrid_changed_rows':int(g.n_per_tag_changed.gt(0).sum())})
    pd.DataFrame(annual_stats).to_csv(OUT/'cohort_annual_counts.csv',index=False)
    coverage = selected.merge(q.groupby('cik').size().rename('eligible_landmarks'),on='cik',how='left')
    coverage['eligible_landmarks'] = coverage.eligible_landmarks.fillna(0).astype(int)
    coverage.to_csv(OUT/'cohort_selected_cik_coverage.csv',index=False)
    summary = {'rows':len(q),'ciks':q.cik.nunique(),'clusters':q.cluster_id.nunique(),'positive_windows':int(q.registry_event_365.sum()),
               'distinct_event_ciks':q.loc[q.registry_event_365.eq(1),'cik'].nunique(),'coherent_later_available':int(q.later_accession.ne('').sum()),
               'coherent_changed_rows':int(q.n_coherent_changed.gt(0).sum()),'hybrid_changed_rows':int(q.n_per_tag_changed.gt(0).sum()),
               'cohort_sha256':hashlib.sha256((DATA/'model_cohort.parquet').read_bytes()).hexdigest(),
               'same_missingness_A_B':bool(np.array_equal(mask_a,mask_b)),'models_fitted_here':0,
               'coverage_by_stratum':coverage.groupby('sampling_stratum').agg(selected_ciks=('cik','size'),eligible_ciks=('eligible_landmarks',lambda s:int(s.gt(0).sum()))).reset_index().to_dict('records')}
    (OUT/'cohort_summary.json').write_text(json.dumps(summary,indent=2,default=int),encoding='utf-8')
    print(json.dumps(summary,default=int),flush=True)

if __name__ == '__main__':
    main()

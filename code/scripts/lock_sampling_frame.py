"""Lock an outcome-stratified sample from the complete historical filing frame.

Joint annual accessions define dependence clusters, not legal enterprise groups.
Every cluster with a BRD-linked CIK is selected with certainty. The remaining
clusters are selected by simple random sampling without replacement. All CIKs
in a selected cluster are retained; outcomes are never propagated to cofilers.
"""
import hashlib
import json
from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / 'datasets'
OUT = ROOT / 'results'
SEED = 20260921
N_CONTROL = 1000

def main():
    destination = DATA / 'sampling_frame.parquet'
    if destination.exists():
        raise FileExistsError('The sampling frame is locked; do not silently redraw it.')
    annual = pd.read_parquet(DATA / 'universe_annual_filings_2010_2021.parquet')
    brd = pd.read_parquet(DATA / 'brd_all_events.parquet')
    ciks = sorted(annual.cik.unique())
    parent = {c:c for c in ciks}
    def find(c):
        while parent[c] != c:
            parent[c] = parent[parent[c]]
            c = parent[c]
        return c
    def union(a,b):
        a,b = find(a),find(b)
        if a != b:
            parent[max(a,b)] = min(a,b)
    for _,group in annual.groupby('accession_number',sort=False):
        members = group.cik.unique()
        for c in members[1:]:
            union(members[0],c)
    frame = pd.DataFrame({'cik':ciks})
    frame['cluster_id'] = frame.cik.map(find)
    # Includes all registry history to prevent already-recorded cases being
    # silently treated as controls. Observation-level censoring is applied later.
    events = brd.loc[brd.cik.ne('') & brd.event_date.le('2022-12-31')].groupby('cik').event_date.min()
    frame['first_registry_event'] = frame.cik.map(events)
    certainty = set(frame.loc[frame.first_registry_event.notna(),'cluster_id'])
    others = sorted(set(frame.cluster_id) - certainty)
    rng = np.random.default_rng(SEED)
    selected_others = set(rng.choice(others,size=min(N_CONTROL,len(others)),replace=False))
    frame['sampling_stratum'] = np.where(frame.cluster_id.isin(certainty),'certainty','noncase_srs')
    frame['selected'] = frame.cluster_id.isin(certainty | selected_others)
    frame['inclusion_probability'] = np.where(frame.sampling_stratum.eq('certainty'),1.0,len(selected_others)/len(others))
    frame['sample_weight'] = 1 / frame.inclusion_probability
    frame.to_parquet(destination,index=False)
    frame.loc[frame.selected].to_csv(DATA/'sampled_ciks.csv',index=False)
    counts = frame.groupby('cluster_id').size()
    summary = {
        'sampling_seed':SEED,'sampling_unit':'connected component of shared annual accessions, 2010–2021',
        'not_a_complete_legal_group_identifier':True,'target_label':'direct CikBefore-linked first BRD event; no co-filer propagation',
        'historical_ciks':len(frame),'historical_clusters':len(counts),'joint_clusters':int(counts.gt(1).sum()),
        'largest_cluster_ciks':int(counts.max()),'certainty_clusters':len(certainty),'noncase_population_clusters':len(others),
        'noncase_sample_clusters':len(selected_others),'selected_ciks':int(frame.selected.sum()),
        'selected_noncase_ciks':int((frame.selected & frame.sampling_stratum.eq('noncase_srs')).sum()),
        'selected_certainty_ciks':int((frame.selected & frame.sampling_stratum.eq('certainty')).sum()),
        'inclusion_probability_noncase':len(selected_others)/len(others),'frame_sha256':hashlib.sha256(destination.read_bytes()).hexdigest(),
        'eligible_observations':'2010–2021 day-after-original-annual-filing landmarks, before first registry event, positive original assets; SEC standard-tag facts accessible at retrieval',
        'eligible_domain_note':'Original-asset observability defines a restricted domain, not a response adjustment; inference does not extend to unavailable XBRL filers.',
        'model_results_seen_before_sampling':False,
    }
    (OUT/'sampling_frame_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
    print(json.dumps(summary),flush=True)

if __name__ == '__main__':
    main()

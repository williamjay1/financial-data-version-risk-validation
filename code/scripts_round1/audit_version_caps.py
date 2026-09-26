"""Independent stored-lineage checks for finite version horizons."""
from pathlib import Path
import sys,json
import numpy as np
import pandas as pd
REV=Path(__file__).resolve().parents[1];ROOT=REV.parent
sys.path.insert(0,str(ROOT/'scripts'))
import run_vintage_models as vm
import build_vintage_panel as vp

def main():
    out=REV/'results/version_caps'
    d=pd.read_parquet(ROOT/'datasets/model_cohort.parquet').set_index(['cik','accession'])
    t=pd.read_parquet(out/'cap_lineage.parquet')
    f=pd.read_parquet(out/'cap_fact_lineage.parquet')
    checks=[]
    def ck(name,condition):
        checks.append({'check':name,'pass':bool(condition)})
        assert condition,name
    def raw_ratios(wide):
        return pd.DataFrame([vp.ratios({k:r.get(k,np.nan) for k in vp.TAGS}) for r in wide.to_dict('records')],index=wide.index)
    for cap in [90,365,730]:
        c=pd.read_parquet(REV/f'datasets/cap_{cap}.parquet').set_index(['cik','accession']).reindex(d.index)
        ck(f'{cap}: row identity',len(c)==len(d) and c.index.equals(d.index))
        ck(f'{cap}: original values unchanged',np.array_equal(c[['A_'+x for x in vm.FEATURES]].to_numpy(),d[['A_'+x for x in vm.FEATURES]].to_numpy(),equal_nan=True))
        ft=f[f.cap_days.eq(cap)]
        ck(f'{cap}: same accession throughout bundle',ft.groupby(['cik','accession']).selected_accession.nunique().eq(1).all())
        lineage=raw_ratios(ft.pivot(index=['cik','accession'],columns='feature',values='capped')).reindex(d.index)
        ck(f'{cap}: ratio reconstruction',np.allclose(lineage[vm.FEATURES],c[['B_'+x for x in vm.FEATURES]],rtol=1e-12,atol=1e-12,equal_nan=True))
        ck(f'{cap}: missing masks',np.array_equal(c[['A_'+x for x in vm.FEATURES]].isna(),c[['B_'+x for x in vm.FEATURES]].isna()))
        tc=t[t.cap_days.eq(cap)]
        use=tc.later_bundle_available
        ck(f'{cap}: source available by deadline',(pd.to_datetime(tc.loc[use,'later_filed'])<=pd.to_datetime(tc.loc[use,'deadline'])).all())
        original_dates=tc.merge(d[['filing_date']].reset_index(),on=['cik','accession'])
        ck(f'{cap}: strictly later than original',(pd.to_datetime(original_dates.loc[use.to_numpy(),'later_filed'])>pd.to_datetime(original_dates.loc[use.to_numpy(),'filing_date'])).all())
    ck('fact unit preserved',f.unit.eq('USD').all())
    origfacts=pd.read_parquet(ROOT/'datasets/vintage_facts.parquet').rename(columns={'original_accession':'accession'})
    linked=f.merge(origfacts[['cik','accession','feature','tag','unit','start','end','A']],on=['cik','accession','feature'],suffixes=('','_original'),validate='many_to_one')
    for col in ['tag','unit','start','end','A']:ck(f'original fact {col} preserved',linked[col].eq(linked[col+'_original']).all())
    w=pd.DataFrame(json.loads((out/'record_filing_date_warnings.json').read_text()))
    j=t.merge(w,left_on=['cik','accession','selected_accession'],right_on=['cik','original_accession','candidate'])
    j['after_deadline']=j.apply(lambda r:max(r.record_dates)>r.deadline,axis=1)
    boundary={'candidate_fact_date_mismatches':len(w),'selected_cap_fact_date_mismatches':len(j),
        'crossed_cap_deadline':int(j.after_deadline.sum()),'selected_landmark_cap_pairs':len(j.drop_duplicates(['cik','accession','cap_days']))}
    ck('API record dates do not cross selected cap deadline',not j.after_deadline.any())
    report={'status':'PASS','checks':checks,'passed':len(checks),'boundary_audit':boundary,
            'script_sha256':vm.sha256(Path(__file__)),'lineage_sha256':vm.sha256(out/'cap_fact_lineage.parquet')}
    vm.write_json(out/'audit.json',report);print(json.dumps(vm.clean_json(report)))

if __name__=='__main__':main()

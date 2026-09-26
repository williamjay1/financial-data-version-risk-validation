"""Read-only audit of uniquely archived FDIC JSON/YAML. No training."""
from pathlib import Path
from datetime import datetime, timezone
import json, hashlib, re
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
RAW = Path('<archived-record-root>/...')

def path_for(suffix):
    paths = sorted(RAW.glob('*_' + suffix))
    if len(paths) != 1:
        raise ValueError(f'Expected one archived {suffix}: {paths}')
    return paths[0]

def read_json(suffix):
    return json.loads(path_for(suffix).read_text(encoding='utf-8'))

def flatten(j):
    return pd.DataFrame([r['data'] for r in j['data']])

def properties(suffix):
    y = yaml.safe_load(path_for(suffix).read_text(encoding='utf-8'))
    return y['properties']['data']['properties']

def save_json(name, value):
    (OUT / name).write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding='utf-8')

def main():
    failure_json = read_json('failures_all.json')
    financial_json = read_json('financial_join_sample.json')
    events = flatten(failure_json)
    reports = flatten(financial_json)
    assert len(events) == failure_json['meta']['total']
    assert len(reports) == financial_json['meta']['total']
    events['failure_date'] = pd.to_datetime(events['FAILDATE'], format='%m/%d/%Y', errors='coerce')
    events['year'] = events.failure_date.dt.year
    reports['report_date'] = pd.to_datetime(reports['REPDTE'].astype(str), format='%Y%m%d', errors='coerce')
    reports['end_date'] = pd.to_datetime(reports['ENDEFYMD'].astype(str), format='%Y%m%d', errors='coerce')
    reports['end_is_sentinel'] = reports['ENDEFYMD'].astype(str).eq('99991231')
    failures = events[events['RESTYPE'].eq('FAILURE')].copy()
    annual = events.groupby(['year', 'RESTYPE']).size().unstack(fill_value=0).reindex(range(int(events.year.min()), 2027), fill_value=0)
    annual.to_csv(OUT / 'bank_events_by_year.csv', encoding='utf-8-sig')
    event_columns = ['CERT','FIN','NAME','FAILDATE','RESDATE','RESTYPE','RESTYPE1','QBFASSET','QBFDEP']
    events[event_columns].to_csv(OUT / 'bank_events_full.csv', index=False, encoding='utf-8-sig')
    joins=[]
    for cert, rs in reports.groupby('CERT'):
        ev = failures[failures.CERT.eq(cert)].sort_values('failure_date')
        fd = ev.failure_date.iloc[-1] if len(ev) else pd.NaT
        pre = rs[rs.report_date.lt(fd)] if pd.notna(fd) else rs.iloc[:0]
        last = pre.sort_values('report_date').iloc[-1] if len(pre) else None
        joins.append({'CERT':int(cert), 'latest_sample_name':rs.sort_values('report_date').NAME.iloc[-1],
          'financial_rows':len(rs), 'first_report':rs.report_date.min().date(), 'last_report':rs.report_date.max().date(),
          'failure_matches':len(ev), 'failure_date':fd.date() if pd.notna(fd) else None,
          'reports_before_failure':len(pre), 'reports_on_or_after_failure':int(rs.report_date.ge(fd).sum()) if pd.notna(fd) else None,
          'last_pre_failure_quarter':last.report_date.date() if last is not None else None,
          'last_pre_failure_ASSET':last.ASSET if last is not None else None,
          'failure_QBFASSET':ev.QBFASSET.iloc[-1] if len(ev) else None,
          'rows_real_ENDEFYMD_after_REPDTE':int((rs.end_date.gt(rs.report_date)&~rs.end_is_sentinel).sum()),
          'rows_ENDEFYMD_sentinel_99991231':int(rs.end_is_sentinel.sum())})
    join_frame=pd.DataFrame(joins)
    join_frame.to_csv(OUT / 'bank_cert_join_sample.csv', index=False, encoding='utf-8-sig')
    fp = properties('financial_dictionary.yaml')
    ep = properties('failure_dictionary.yaml')
    timekeys = [k for k in fp if re.search('DATE|DTE|YMD|UPDT|SUBMI|PUBL|VINTAG', k)]
    dictionary = {'financial_field_count':len(fp), 'failure_field_count':len(ep),
      'financial_date_named_fields':{k:fp[k] for k in timekeys},
      'financial_key_fields':{k:fp.get(k) for k in ['CERT','RSSDID','REPDTE','RISDATE','EFFDATE','ENDEFYMD','ACTIVE','ACTEVT','ASSET','DEP','EQ','NETINC','ROA','ROE','DEPUNINS']},
      'failure_key_fields':{k:ep.get(k) for k in ['CERT','FIN','FAILDATE','RESDATE','RESTYPE','RESTYPE1','QBFASSET','QBFDEP','COST','COSTMOSTRECENTASOF']}}
    save_json('bank_selected_dictionary.json', dictionary)
    swagger=yaml.safe_load(path_for('swagger.yaml').read_text(encoding='utf-8'))
    params=swagger['paths']['/financials']['get']['parameters']
    resolved=[]
    for p in params:
        if '$ref' in p:
            item=swagger
            for k in p['$ref'].split('/')[1:]:item=item[k]
            resolved.append(item)
        else:resolved.append(p)
    save_json('bank_financial_endpoint_parameters.json', resolved)
    first=read_json('financial_first_date.json')
    last=read_json('financial_last_date.json')
    svb=reports[reports.CERT.eq(24735)&reports.REPDTE.eq('20221231')]
    summary={
      'audited_utc':datetime.now(timezone.utc).isoformat(),
      'scope':'All failure/assistance records; financial sample deliberately selected 12 recently failed banks and 3 controls, not representative risk set.',
      'failure_endpoint':{'retrieved_rows':len(events),'declared_total':failure_json['meta']['total'],
        'min_date':events.failure_date.min().date(),'max_date':events.failure_date.max().date(),
        'invalid_dates':int(events.failure_date.isna().sum()),'type_counts':events.RESTYPE.value_counts().to_dict(),
        'transaction_counts':events.RESTYPE1.value_counts().to_dict(),'CERT_missing':int(events.CERT.isna().sum()),
        'CERT_zero':int(events.CERT.eq(0).sum()),'distinct_CERT':int(events.CERT.nunique()),
        'CERT_missing_since_1984':int(events.loc[events.year.ge(1984),'CERT'].isna().sum()),
        'duplicate_CERT_rows':int(events.duplicated('CERT',keep=False).sum()),
        'duplicate_CERT_FAILDATE_FIN_rows':int(events.duplicated(['CERT','FAILDATE','FIN'],keep=False).sum()),
        'duplicate_known_CERT_FAILDATE_FIN_rows':int(events[events.CERT.notna()].duplicated(['CERT','FAILDATE','FIN'],keep=False).sum()),
        'failure_counts_since':{str(y):int(failures.year.ge(y).sum()) for y in [1984,1992,2000,2010,2015,2020]},
        'meta':failure_json['meta']},
      'global_financial_endpoint':{'declared_rows':first['meta']['total'],
        'earliest_REPDTE':first['data'][0]['data']['REPDTE'],'latest_REPDTE':last['data'][0]['data']['REPDTE'],
        'caution':'Observed endpoint dates do not establish complete coverage for each predictor.'},
      'sample_financials':{'rows':len(reports),'distinct_CERT':int(reports.CERT.nunique()),
        'duplicate_CERT_REPDTE_rows':int(reports.duplicated(['CERT','REPDTE'],keep=False).sum()),
        'invalid_report_dates':int(reports.report_date.isna().sum()),
        'failed_CERT_matched':int(join_frame.failure_matches.gt(0).sum()),
        'matched_failure_count_max_per_CERT':int(join_frame.failure_matches.max()),
        'rows_with_future_ENDEFYMD':int(reports.end_date.gt(reports.report_date).sum()),
        'rows_with_real_future_ENDEFYMD':int((reports.end_date.gt(reports.report_date)&~reports.end_is_sentinel).sum()),
        'rows_ENDEFYMD_sentinel_99991231':int(reports.end_is_sentinel.sum()),
        'failed_CERT_last_report_ASSET_differs_QBFASSET':int((join_frame.failure_matches.gt(0)&join_frame.last_pre_failure_ASSET.ne(join_frame.failure_QBFASSET)).sum()),
        'rows_with_REPDTE_ne_RISDATE':int(reports.REPDTE.ne(reports.RISDATE).sum()),
        'SVB_2022Q4':svb.drop(columns=['report_date','end_date','end_is_sentinel']).to_dict(orient='records'),
        'meta':financial_json['meta']},
      'schema':{'actual_failure_columns':list(flatten(failure_json).columns),
        'actual_financial_sample_columns':list(flatten(financial_json).columns),
        'dictionary_financial_fields':len(fp),'dictionary_failure_fields':len(ep),
        'date_named_financial_fields':timekeys,
        'financial_endpoint_parameter_names':[p.get('name') for p in resolved]},
      'point_in_time_status':'Not established. REPDTE/RISDATE are reporting periods; current index timestamp is not original publication. No vintage/as-of query parameter documented in audited financial endpoint.'}
    save_json('bank_audit_summary.json',summary)
    logs=[]
    for f in sorted(OUT.glob('bank_download_log_*.json')):
        entries=json.loads(f.read_text(encoding='utf-8'))
        for e in entries:
            if 'raw_path' not in e:logs.append(e);continue
            p=Path(e['raw_path']);h=hashlib.sha256(p.read_bytes()).hexdigest()
            assert h==e['sha256'],p
            e['hash_verified']=True
            e['filesystem_readonly']=not bool(p.stat().st_mode & 0o200)
            logs.append(e)
    save_json('bank_raw_manifest.json',logs)
    print(json.dumps(summary,ensure_ascii=False,default=str,indent=2))
    print('JOIN',join_frame.to_string(index=False))
    print('RECENT',annual.loc[2000:].to_string())

if __name__=='__main__':main()

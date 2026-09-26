from pathlib import Path
from datetime import datetime,timezone
from urllib.parse import urlencode
import requests,json,hashlib
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'results'
RAW=Path('<archived-record-root>/...')
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
certs=[24735,57053,59017,8758,25851,27332,4134,28611,5520,57488,25796,25744,628,3510,3511]
params={'filters':'CERT:('+' OR '.join(map(str,certs))+')','fields':'CERT,REPDTE,RISDATE,NAME,ASSET,DEP,EQ,NETINC,ROA,ROE,LNLSNET,DEPUNINS,ENDEFYMD,EFFDATE,ACTIVE,ID','limit':10000,'sort_by':'REPDTE','sort_order':'ASC','format':'json'}
urls={
 'financial_dictionary.yaml':'https://api.fdic.gov/banks/docs/risview_properties.yaml',
 'failure_dictionary.yaml':'https://api.fdic.gov/banks/docs/failure_properties.yaml',
 'institution_dictionary.yaml':'https://api.fdic.gov/banks/docs/institution_properties.yaml',
 'swagger.yaml':'https://api.fdic.gov/banks/docs/swagger.yaml',
 'financial_join_sample.json':'https://api.fdic.gov/banks/financials?'+urlencode(params),
 'financial_first_date.json':'https://api.fdic.gov/banks/financials?fields=CERT,REPDTE&limit=1&sort_by=REPDTE&sort_order=ASC&format=json',
 'financial_last_date.json':'https://api.fdic.gov/banks/financials?fields=CERT,REPDTE&limit=1&sort_by=REPDTE&sort_order=DESC&format=json',
}
log=[]
for name,url in urls.items():
 try:
  r=requests.get(url,timeout=45);path=RAW/(stamp+'_'+name)
  with path.open('xb') as f:f.write(r.content)
  path.chmod(0o444)
  d={'name':name,'url':url,'final_url':r.url,'http_status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'raw_path':str(path),'retrieved_utc':datetime.now(timezone.utc).isoformat()};log.append(d)
  print(json.dumps(d),flush=True)
  if name.endswith('.json') and r.status_code==200:
   j=r.json();print('META',json.dumps(j.get('meta')),'N',len(j.get('data',[])),flush=True)
   if len(j.get('data',[]))<2:print('DATA',json.dumps(j.get('data')),flush=True)
 except Exception as e:log.append({'name':name,'url':url,'error':repr(e)});print('ERROR',name,repr(e),flush=True)
(OUT/('bank_download_log_'+stamp+'.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')

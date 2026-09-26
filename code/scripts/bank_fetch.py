"""Official FDIC feasibility downloads only; immutable new raw names on E."""
from pathlib import Path
from datetime import datetime,timezone
import json,re,hashlib,os
import requests
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results';OUT.mkdir(parents=True,exist_ok=True)
RAW=Path('<archived-record-root>/...')
RAW.mkdir(parents=True,exist_ok=True)
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
urls={
 'api_docs.html':'https://api.fdic.gov/banks/docs/',
 'failures_all.json':'https://api.fdic.gov/banks/failures?limit=10000&sort_by=FAILDATE&sort_order=DESC&format=json',
 'financials_full_schema_sample.json':'https://api.fdic.gov/banks/financials?filters=CERT%3A24735&limit=2&sort_by=REPDTE&sort_order=DESC&format=json',
}
log=[]
for name,url in urls.items():
 try:
  r=requests.get(url,timeout=45)
  path=RAW/(stamp+'_'+name)
  with path.open('xb') as f:f.write(r.content)
  path.chmod(0o444)
  entry={'name':name,'url':url,'final_url':r.url,'http_status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'raw_path':str(path),'content_type':r.headers.get('Content-Type'),'retrieved_utc':datetime.now(timezone.utc).isoformat()}
  log.append(entry)
  print(json.dumps(entry))
  if name=='api_docs.html':print('LINKS',json.dumps(re.findall(r'href=[\"\']([^\"\']+)',r.text)))
  elif r.status_code==200:
   j=r.json();print('META',json.dumps(j.get('meta')),'TOTALS',json.dumps(j.get('totals')))
   if j.get('data'):print('FIRST_RECORD',json.dumps(j['data'][0])[:15000])
 except Exception as e:
  log.append({'name':name,'url':url,'error':repr(e)})
  print('ERROR',name,repr(e))
(OUT/('bank_download_log_'+stamp+'.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')

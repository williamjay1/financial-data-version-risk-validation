"""Archive a bounded set of official documentation; exclusive new raw filenames."""
from pathlib import Path
from datetime import datetime,timezone
import requests,json,hashlib
ROOT=Path(__file__).resolve().parents[1]
RAW=Path('<archived-record-root>/...')
stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
urls={
 'ffiec_public_service.pdf':'https://cdr.ffiec.gov/public/Files/SIS611_-_Retrieve_Public_Data_via_Web_Service.pdf',
 'ffiec_pws_info.html':'https://cdr.ffiec.gov/public/HelpFiles/PWSInfo.htm',
 'fdic_api_catalog_license.html':'https://catalog.data.gov/dataset/fdic-bankfind-suite-api',
 'ffiec_revision_history.html':'https://cdr.ffiec.gov/CDR/public/CDRHelp/Managing%20Call%20Reports%201%20(F1PSJ25%20v1).htm'
}
log=[]
for name,url in urls.items():
 try:
  r=requests.get(url,timeout=40)
  p=RAW/(stamp+'_'+name)
  with p.open('xb') as f:f.write(r.content)
  p.chmod(0o444)
  row={'name':name,'url':url,'final_url':r.url,'http_status':r.status_code,'bytes':len(r.content),'sha256':hashlib.sha256(r.content).hexdigest(),'raw_path':str(p),'retrieved_utc':datetime.now(timezone.utc).isoformat()}
  log.append(row);print(json.dumps(row),flush=True)
 except Exception as exc:
  log.append({'name':name,'url':url,'error':repr(exc)});print(repr(exc),flush=True)
(ROOT/'results'/('bank_download_log_'+stamp+'.json')).write_text(json.dumps(log,indent=2),encoding='utf-8')

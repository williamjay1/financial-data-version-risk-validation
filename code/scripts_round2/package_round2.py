"""Local round-two analysis handover. Default DRAFT; final requires explicit freeze."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,importlib.util,io,json,os,shutil,sys,zipfile
sys.dont_write_bytecode=True
REV=Path(__file__).resolve().parents[1]; ROOT=REV.parent; OLD=ROOT/'revision_20260922'
REPRO=REV/'reproducibility';DELIVERY=REV/'deliverables'
spec=importlib.util.spec_from_file_location('readonly_previous_package',OLD/'scripts/package_revision.py')
previous=importlib.util.module_from_spec(spec);spec.loader.exec_module(previous)

def sha(path):return previous.digest(path)
def longpath(path):
    value=str(Path(path).resolve())
    return Path(chr(92)*2+'?'+chr(92)+value) if os.name=='nt' and not value.startswith(chr(92)*2+'?') else Path(value)
def textkey(key):
    key=key.lower()
    return key in previous.EXCERPT_KEYS or key.endswith('_excerpt') or key.endswith('_full_text')
def redact(value):
    if isinstance(value,dict):return {k:redact(v) for k,v in value.items() if not textkey(k)}
    if isinstance(value,list):return [redact(v) for v in value]
    return value
def candidates():
    inherited,excluded,_=previous.candidates(); files=set()
    for p in inherited:
        # Older prose and rendering remain in the source project; retain bibliographies
        # and analytical code/data needed by the current manuscript.
        if 'manuscript' in p.parts and p.suffix!='.bib':continue
        if p.parent==OLD/'reproducibility' and p.name not in ['reproduce.py','requirements-lock.txt','environment.json','data_dictionary.md']:continue
        files.add(p)
    for folder in ['scripts','datasets','results','figures','manuscript','literature']:
        for p in (REV/folder).rglob('*'):
            if not p.is_file():continue
            parts=p.relative_to(REV).parts;reason=None
            if '__pycache__' in parts or p.suffix in ['.pyc','.lock']:reason='runtime/cache file'
            elif any('superseded' in x for x in parts[:-1]):reason='superseded run'
            elif folder in ['literature'] and p.suffix.lower() in ['.txt','.html','.xml','.pdf']:reason='third-party source text'
            elif 'source_semantics' in parts and p.suffix.lower() in ['.txt','.html','.xml','.pdf']:reason='third-party filing/taxonomy full text'
            elif 'source_text' in parts:reason='third-party source text'
            if reason:excluded.append({'path':str(p.relative_to(ROOT)),'reason':reason})
            else:files.add(p)
    for p in REV.glob('*.md'):files.add(p)
    # The supplement has a few additional frozen source summaries beyond the
    # previous package's candidate list. Include every declared local dependency.
    dependency_map=REV/'results/supplement_tables/numeric_source_mapping.json'
    if dependency_map.exists():
        declared=json.loads(dependency_map.read_text(encoding='utf-8'))['sources']
        for relative,expected in declared.items():
            p=(ROOT/relative).resolve()
            assert p.is_relative_to(ROOT.resolve()) and p.is_file(),relative
            assert sha(p)==expected,('Supplement source changed after assembly',relative)
            files.add(p)
    for p in REPRO.iterdir():
        if not p.is_file():continue
        # Package-specific validation is issued externally after the ZIP is built.
        # Keeping it out avoids circular hashes and stale DRAFT verdicts.
        stale=p.name in ['latest_package.json','final_package_validation.json','final_package_validation.md',
                         'portable_validation.json','portable_validation.md','main_manuscript_bounded_audit.json',
                         'supplement_visual_qa_18_25.json'] or p.name.startswith('portable_smoke_')
        if stale:excluded.append({'path':str(p.relative_to(ROOT)),'reason':'external package validation or superseded draft audit'})
        else:files.add(p)
    return sorted(files),excluded

def copy_file(source,target):
    raw=source.read_bytes(); sourcehash=hashlib.sha256(raw).hexdigest();transform=None
    sensitive=any(x in source.parts for x in ['source_audit','source_semantics']) or source.name=='verified_corrections_snapshot.csv'
    if sensitive and source.suffix=='.csv':
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))); headers=reader.fieldnames or []; drop=[k for k in headers if textkey(k)]
        if drop:
            buf=io.StringIO(newline='');w=csv.DictWriter(buf,fieldnames=[k for k in headers if k not in drop],lineterminator='\n');w.writeheader()
            w.writerows({k:v for k,v in row.items() if k not in drop} for row in reader)
            raw=buf.getvalue().encode('utf-8');transform={'operation':'omit third-party excerpt columns','columns':drop}
    elif sensitive and source.suffix=='.json':
        original=json.loads(raw.decode('utf-8-sig'));cleaned=redact(original)
        if original!=cleaned:raw=json.dumps(cleaned,ensure_ascii=False,indent=2).encode('utf-8');transform='omit third-party text keys'
    target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(raw)
    assert sha(source)==sourcehash,'Source changed while copying: '+str(source)
    return {'source_sha256':sourcehash,'package_sha256':sha(target),'bytes':len(raw),'transformation':transform}

def build(final=False,freeze=False):
    assert shutil.disk_usage(REV).free>5*1024**3
    for name in ['development_controls/run_manifest.json','fit_date/manifest.json','scale_only/manifest.json','evaluation_diagnostics/manifest.json']:
        assert (REV/'results'/name).is_file(),name
    if final:
        assert freeze,'Explicit parent/user final freeze required'
        assert any((REV/'manuscript').glob('*.docx')),'Final Word manuscript absent'
        audit=json.loads((REV/'results/final_revision_audit.json').read_text(encoding='utf-8'))
        assert str(audit['status']).startswith('PASS'),'Final delivery audit not passed'
        summary=json.loads((REV/'manuscript/content_summary.json').read_text(encoding='utf-8'))
        assert summary['sha256']==sha(REV/'manuscript/manuscript.md')
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ');mode='FINAL' if final else 'DRAFT'
    stage=longpath(REPRO/'staging'/stamp/'study');stage.mkdir(parents=True,exist_ok=False)
    files,excluded=candidates();entries=[]
    for source in files:
        relative=source.relative_to(ROOT);entry=copy_file(source,stage/relative);entry['path']=relative.as_posix();entries.append(entry)
    entry=copy_file(REPRO/'README.md',stage/'README.md');entry['path']='README.md';entries.append(entry)
    ledger={'status':'local_research_handover_not_public_data_release','excluded':excluded,
      'raw_archives_excluded':['SEC companyfacts and submissions originals/large cache','BRD raw registry','original filing/taxonomy HTML/XML/full text','internal Word rendering PDF/PNG'],
      'access_routes':[
        {'source':'SEC EDGAR API','url':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces'},
        {'source':'SEC original filings','url':'https://www.sec.gov/Archives/edgar/data/'},
        {'source':'BRD','url':'https://lopucki.law.ufl.edu/'},
        {'source':'historical frame mirror','url':'https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024'},
        {'source':'BLS CPI-U NSA','url':'https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0'}],
      'rights':'No license grant over third-party or derived data. Review source terms before public redistribution. No upload or DOI is performed.',
      'provenance':'Archived absolute paths are historical metadata only. Redacted copies have package hashes distinct from source hashes; original hashes remain in lineage.'}
    ledgerpath=stage/'SOURCE_ACCESS_AND_EXCLUSIONS.json';ledgerpath.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    entries.append({'path':ledgerpath.name,'source_sha256':None,'package_sha256':sha(ledgerpath),'bytes':ledgerpath.stat().st_size,'transformation':'generated access ledger'})
    manifest={'status':mode,'created_utc':datetime.now(timezone.utc).isoformat(),'active_entry':'revision_20260922_round2/reproducibility/reproduce.py',
      'default_action':'offline metrics and perturbation recalculation; no model fitting or raw download',
      'supported_correction':'22 scale-supported contexts; four sign claims unresolved; historical 26-context sensitivity retained in previous round only',
      'formal_refit_replicates':200,'files':entries}
    (stage/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    DELIVERY.mkdir(exist_ok=True);archive=DELIVERY/f'Financial_Vintage_Round2_{mode}_{stamp}.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,Path('study')/p.relative_to(stage))
    result={'mode':mode,'stage':str(stage),'zip':str(archive),'zip_bytes':archive.stat().st_size,'zip_sha256':sha(archive),
      'included_files':len(entries)+1,'package_manifest_sha256':sha(stage/'PACKAGE_MANIFEST.json'),'validation':'pending extracted-copy offline execution'}
    (REPRO/'latest_package.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result),flush=True)
    return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');parser.add_argument('--freeze-confirmed',action='store_true');a=parser.parse_args();build(a.final,a.freeze_confirmed)

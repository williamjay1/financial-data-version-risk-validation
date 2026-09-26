"""Build a local portable analysis package; never publish or copy raw originals.

Default creates a draft. --final --freeze-confirmed requires all 200 formal
refitting draws and a final manuscript. A root-authorized final freeze is required.
"""
from pathlib import Path
from datetime import datetime,timezone
import argparse,csv,hashlib,importlib.metadata,io,json,shutil,sys,zipfile
REV=Path(__file__).resolve().parents[1]; ROOT=REV.parent
REPRO=REV/'reproducibility'; DELIVERY=REV/'deliverables'
EXCERPT_KEYS={'source_excerpt','display_excerpt','heading_excerpt','excerpt','text','content','html','snippet','line'}

def digest(path):
    h=hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda:f.read(1048576),b''):h.update(block)
    return h.hexdigest()

def redact_json(value):
    if isinstance(value,dict):return {k:redact_json(v) for k,v in value.items() if k.lower() not in EXCERPT_KEYS}
    if isinstance(value,list):return [redact_json(v) for v in value]
    return value

def candidates():
    files=set(); exclusions=[]
    def add(path):
        if path.is_file():files.add(path)
    for p in (ROOT/'scripts').glob('*.py'):add(p)
    for name in ['model_cohort','sampling_frame','vintage_facts','vintage_panel','universe_annual_filings_2010_2021',
                 'sensitivity_source_scale_corrected','sensitivity_no_transition']:
        add(ROOT/'datasets'/f'{name}.parquet')
    add(ROOT/'phase2_protocol.json')
    for p in (ROOT/'manuscript').iterdir():
        if p.is_file() and p.suffix in ['.md','.bib','.docx','.json']:add(p)
    index=json.loads((ROOT/'results/final_run_index.json').read_text(encoding='utf-8'))
    for item in index['model_runs']+index['uncertainty_runs']:
        manifest=Path(item['manifest']); prefix=manifest.name.removesuffix('_manifest.json')
        for p in manifest.parent.glob(prefix+'*'):add(p)
    for pattern in ['final_*','cohort_*','sampling_frame_summary.json','sensitivity_design.json','universe_artifact_manifest.json',
                    'universe_sraf_count_crosscheck.csv','control_sec_*manifest*.jsonl','expanded_sec_*manifest*.jsonl','corporate_access_manifest*.json']:
        for p in (ROOT/'results').glob(pattern):add(p)
    oldfig=Path(index['figure_directory'])
    for p in oldfig.iterdir():add(p)
    add(REV/'REVISION_PROTOCOL.md')
    for folder in ['scripts','datasets','results','figures','manuscript','literature']:
        for p in (REV/folder).rglob('*'):
            if not p.is_file():continue
            relative=p.relative_to(REV)
            parts=relative.parts
            reason=None
            if '__pycache__' in parts or p.suffix in ['.pyc','.lock']:reason='runtime cache or in-flight lock'
            elif any('superseded' in s for s in parts[:-1]):reason='superseded exploratory run; not a final result'
            elif 'source_text' in parts or p.name=='display_navigation.json':reason='third-party full text or navigation excerpts'
            elif folder=='literature' and p.suffix in ['.txt','.html','.pdf']:reason='third-party source text'
            elif 'corrected_models' in parts and not p.name in ['design.json','manifest.json','superseded_by_v2.json','applied_fact_changes.csv']:reason='superseded 15-item correction run; final 26-item v2 included'
            elif folder=='datasets' and p.name in ['source_verified_corrected.parquet','source_verified_corrected_facts.parquet']:reason='superseded 15-item derived cache'
            if reason:exclusions.append({'path':str(p.relative_to(ROOT)),'reason':reason});continue
            add(p)
    for p in REPRO.iterdir():
        if p.is_file() and p.name not in ['latest_package.json']:add(p)
    return sorted(files),exclusions,index

def copy_one(source,dest):
    raw=source.read_bytes(); original=hashlib.sha256(raw).hexdigest(); transform=None
    is_audit=('source_audit' in source.parts or source.name in ['verified_corrections_snapshot.csv','verified_corrections_v1.csv'])
    if is_audit and source.suffix=='.csv':
        reader=csv.DictReader(io.StringIO(raw.decode('utf-8-sig'))); headers=reader.fieldnames or []
        removed=[k for k in headers if k.lower() in EXCERPT_KEYS]
        if removed:
            stream=io.StringIO(newline=''); writer=csv.DictWriter(stream,fieldnames=[k for k in headers if k not in removed],lineterminator='\n')
            writer.writeheader(); writer.writerows({k:v for k,v in row.items() if k not in removed} for row in reader)
            raw=stream.getvalue().encode('utf-8'); transform={'operation':'omit third-party excerpt columns','removed_columns':removed}
    elif is_audit and source.suffix=='.json':
        parsed=json.loads(raw.decode('utf-8-sig')); cleaned=redact_json(parsed)
        if parsed!=cleaned:
            raw=json.dumps(cleaned,ensure_ascii=False,indent=2).encode('utf-8'); transform={'operation':'omit third-party excerpt/text keys recursively'}
    dest.parent.mkdir(parents=True,exist_ok=True); dest.write_bytes(raw)
    assert digest(source)==original,'Source changed during copy; rerun a new draft: '+str(source)
    return {'source_sha256':original,'package_sha256':digest(dest),'bytes':len(raw),'transformation':transform}

def build(final=False,freeze_confirmed=False):
    assert shutil.disk_usage(REV).free>2*1024**3,'Need at least 2 GiB working space'
    uncertainty=REV/'results/uncertainty'
    completed=sum((uncertainty/'replicates'/f'replicate_{i:03d}'/'completed.json').is_file() for i in range(200))
    manifestpath=uncertainty/'manifest.json'
    formal=json.loads(manifestpath.read_text(encoding='utf-8')) if manifestpath.exists() else {}
    contentpath=REV/'manuscript/content_summary.json'
    content=json.loads(contentpath.read_text(encoding='utf-8')) if contentpath.exists() else {}
    if final:
        assert freeze_confirmed,'Final packaging requires explicit root/user freeze confirmation'
        assert completed==200 and formal.get('n_replicates')==200 and formal.get('status')=='COMPLETE','Formal refitting analysis has not completed 200 draws'
        assert (REV/'scripts/assemble_revision.py').exists(),'Final manuscript assembler missing'
        assert any((REV/'manuscript').glob('*.docx')),'Final Word manuscript missing'
        assert (REV/'manuscript/大修落实说明.md').is_file(),'Chinese revision response missing'
        assert (REV/'results/final_delivery_audit.json').is_file(),'Final delivery audit missing'
        assert content.get('sha256')==digest(REV/'manuscript/manuscript.md'),'Manuscript summary hash does not match current manuscript'
        assert content.get('cited_references')==37 and content.get('tables')==12 and content.get('figures')==6,'Frozen manuscript counts differ from the confirmed delivery'
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ'); mode='FINAL' if final else 'DRAFT'
    stage=REPRO/'staging'/stamp/'study'; stage.mkdir(parents=True,exist_ok=False)
    paths,excluded,index=candidates(); entries=[]
    for source in paths:
        relative=source.relative_to(ROOT); row=copy_one(source,stage/relative); row['path']=relative.as_posix(); entries.append(row)
    # Convenience entry/readme at the archive root; canonical entry remains under revision.
    readme=(REPRO/'README.md').read_bytes(); (stage/'README.md').write_bytes(readme)
    entries.append({'path':'README.md','source_sha256':digest(REPRO/'README.md'),'package_sha256':digest(stage/'README.md'),'bytes':len(readme),'transformation':None})
    ledger={'status':'local_analysis_handover_not_public_release','included':'Frozen analytical data, selected fact contexts, code, predictions, fits and audit metadata',
            'excluded':'SEC companyfacts/submissions originals, full BRD source download, source filing HTML/XML/full text, full historical master-index archives, large SEC cache',
            'retrieval_routes':[
                {'source':'SEC EDGAR company facts/submissions','url':'https://www.sec.gov/search-filings/edgar-application-programming-interfaces','note':'Follow SEC fair-access policy; current responses need not equal the archived reconstruction vintage.'},
                {'source':'SEC original filing documents','url':'https://www.sec.gov/Archives/edgar/data/','note':'Exact source URLs, accession/tag/period/unit and archived hashes retained in source-audit tables.'},
                {'source':'Florida-UCLA BRD','url':'https://lopucki.law.ufl.edu/','note':'Review current terms and access conditions; this local package is not permission to redistribute the underlying registry.'},
                {'source':'SEC historical master-index mirror used for the frame','url':'https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024','note':'Exact shard hashes and retrieval evidence are retained in the original universe manifests; the data card does not establish unrestricted redistribution rights.'},
                {'source':'Notre Dame SRAF independent index-count crosscheck','url':'https://sraf.nd.edu/sec-edgar-data/master-index-data/','note':'SRAF count table supports the annual/form coverage crosscheck; the full SRAF archive was not the successfully acquired frame source.'},
                {'source':'BLS CPI-U NSA','url':'https://api.bls.gov/publicAPI/v2/timeseries/data/CUUR0000SA0','note':'Included parsed CPI cache plus URL/hash manifest; raw responses stay outside the package.'}],
            'copyright_handling':'Audit excerpt columns and embedded third-party text are omitted; identity, numeric evidence, locators, source URLs and hashes retained.',
            'licensing':'No new license grant over third-party or derived data. Check source terms and obtain required permissions before public redistribution or commercial use.',
            'historical_absolute_paths':'Retained only in historical provenance; the active reproduce.py entry uses relative paths.',
            'excluded_paths':excluded}
    ledgerpath=stage/'SOURCE_ACCESS_AND_EXCLUSIONS.json'; ledgerpath.write_text(json.dumps(ledger,ensure_ascii=False,indent=2),encoding='utf-8')
    entries.append({'path':ledgerpath.name,'source_sha256':None,'package_sha256':digest(ledgerpath),'bytes':ledgerpath.stat().st_size,'transformation':'generated access/exclusion ledger'})
    manifest={'status':mode,'created_utc':datetime.now(timezone.utc).isoformat(),'formal_refit_draws_at_packaging':completed,
              'manuscript_content_summary':content,
              'final_delivery_audit_sha256':digest(REV/'results/final_delivery_audit.json') if (REV/'results/final_delivery_audit.json').is_file() else None,
              'frozen_main_sha256':'724122d3ca7a0a123de244112aa604d6da7a008497cc6ce526f8f07327916e21',
              'active_entry':'revision_20260922/reproducibility/reproduce.py','default_action':'offline data/result verification and figure/table rebuilding, no training',
              'final_corrections':'26-item corrected_models_v2; 15-item results superseded','files':entries}
    (stage/'PACKAGE_MANIFEST.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf-8')
    DELIVERY.mkdir(exist_ok=True); archive=DELIVERY/f'Financial_Vintage_Revision_{mode}_{stamp}.zip'
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(stage.rglob('*')):
            if p.is_file():z.write(p,Path('study')/p.relative_to(stage))
    result={'mode':mode,'stage':str(stage),'zip':str(archive),'zip_sha256':digest(archive),'zip_bytes':archive.stat().st_size,
            'included_files':len(entries)+1,'formal_refit_draws_at_packaging':completed,
            'smoke_status':'pending; run active entry on staged or extracted copy','package_manifest_sha256':digest(stage/'PACKAGE_MANIFEST.json')}
    (REPRO/'latest_package.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    print(json.dumps(result),flush=True); return result

if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--final',action='store_true');parser.add_argument('--freeze-confirmed',action='store_true');args=parser.parse_args()
    build(args.final,args.freeze_confirmed)

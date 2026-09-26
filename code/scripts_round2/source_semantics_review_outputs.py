"""Read-only review aggregation; never edits source data, manuscript, or models."""
from pathlib import Path
import hashlib
import json
import pandas as pd

ROOT = Path('<working-tree-root>/...')
REV = ROOT / 'revision_20260922_round2'
OUT = REV / 'results/source_semantics'

def read(name):
    return pd.read_csv(OUT/name, dtype=str).fillna('')

def digest(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

trace = read('source_keys_to_components_features_stages.csv')
landmarks = read('targeted_landmarks.csv').set_index('cik')
names = {'0001409916':'Nobilis Health', '0000868725':'Rentech', '0001310497':'Silver Stream Mining',
         '0000786110':'Gymboree', '0001211351':'RTW Retailwinds', '0001568832':'RCS Capital',
         '0001632970':'American Healthcare REIT', '0000278041':'International Shipholding',
         '0001064728':'Peabody Energy', '0001066923':'Future FinTech', '0001076682':'Majesco'}
records=[]
for fn,kind in [('scale_supported_corrections.csv','scale_display_supported'),('author_pending_sign_confirmation.csv','sign_unresolved')]:
    for _,r in read(fn).iterrows():
        match=trace.copy()
        for col in ['cik','source_accession','tag','start','end','unit']:
            match=match[match[col].eq(r[col])]
        records.append(dict(company=names.get(r['cik'],''),cik=r['cik'],review_category=kind,
            source_accession=r['source_accession'],tag=r['tag'],start=r['start'],end=r['end'],unit=r['unit'],
            api_value=r['api_value'],display_normalized_value=r['display_normalized_value'],
            evidence_url=r['evidence_url'],locator=r['locator'],evidence_excerpt=r['source_excerpt'],
            evidence_capture=r['source_raw_path'],evidence_sha256=r['source_raw_sha256'],
            row_ids=';'.join(sorted(set(match.row_id))),arms=';'.join(sorted(set(match.arm))),
            original_stages=';'.join(sorted(set(match.original_stages))),
            affected_main_features=';'.join(sorted(set(match.changed_AB_model_features))),
            interpretation=('Statements display thousands; uniform scaling cancels matched ratios; main A/B changes are log assets only.' if kind.startswith('scale') else r['economic_interpretation']),
            current_analysis_decision=('Display-supported scale sensitivity only; not issuer-XBRL authenticated.' if kind.startswith('scale') else r['default_analysis_decision']),
            source_status=r['status'],input_ledger=fn))
for _,r in read('targeted_new_display_verification.csv').iterrows():
    records.append(dict(company=names.get(r['cik'],''),cik=r['cik'],review_category='targeted_mechanism_display_check',
        source_accession=r['source_accession'],tag=r['tag'],start=r['start'],end=r['end'],unit=r['unit'],
        api_value=r['api_value'],display_normalized_value=r['display_normalized_value'],
        evidence_url=r['source_url'],locator=r['locator'],evidence_excerpt=r['mechanism'],
        evidence_capture=r['evidence_capture'],evidence_sha256=r['evidence_capture_sha256'],
        row_ids=r['row_id'],arms=r['arm'],original_stages=r['original_stages'],affected_main_features=r['feature'],
        interpretation=r['mechanism'],current_analysis_decision='Retain values; adjudicate reporting scope and mechanism; no new numerical correction proposed.',
        source_status=r['status'],input_ledger='targeted_new_display_verification.csv'))
for _,r in read('targeted_prior_display_verification_reused.csv').iterrows():
    lm=landmarks.loc[r['cik']]
    records.append(dict(company=names.get(r['cik'],r['company_name']),cik=r['cik'],review_category='targeted_reused_display_check',
        source_accession=r['source_accession'],tag=r['tag'],start=r['start'],end=r['end'],unit=r['unit'],
        api_value=r['api_value'],display_normalized_value=r['display_normalized_value'],
        evidence_url=r['source_url'],locator='Captured source text character offset '+r['row_char_offset'],
        evidence_excerpt=r['heading_excerpt']+'\n'+r['display_excerpt'],
        evidence_capture=r['source_raw_path'],evidence_sha256=r['source_raw_sha256'],
        row_ids=lm['row_id'],arms=r['arm'],original_stages=lm['original_stages'],affected_main_features=r['feature'],
        interpretation=r['scope_and_access_notes'],current_analysis_decision='Retain values; confirm scope or unchanged inputs; no new numerical correction proposed.',
        source_status=r['display_status']+'; '+r['original_xbrl_status'],input_ledger='targeted_prior_display_verification_reused.csv'))
d=pd.DataFrame(records)
d.insert(0,'confirmation_id',[f'AUTH-{i:03d}' for i in range(1,len(d)+1)])
d['verification_mode']='AI-assisted source reading; no independent human confirmation completed'
d['original_issuer_instance_context_presentation_chain']='NOT_AUTHENTICATED'
d['author_decision_options']='ACCEPT_DISPLAY_ONLY_INTERPRETATION | REVISE_WITH_EVIDENCE | AUTHENTICATE_ISSUER_CHAIN | UNRESOLVED'
for col in ['author_name','author_review_date','author_selected_decision','author_source_locator','author_explanation','author_signature']:
    d[col]=''
d.to_csv(OUT/'author_pending_all_consequential_sources.csv', index=False,encoding='utf-8-sig')

metrics=[]
for label,path,tuned,fixed in [
    ('Unadjusted',ROOT/'revision_20260922/results/models/metrics.csv','original_four_cell','fixed_full'),
    ('Scale supported',REV/'results/scale_only/metrics.csv','source_corrected_tuned','source_corrected_fixed'),
    ('Scale + disputed signs',ROOT/'revision_20260922/results/corrected_models_v2/metrics.csv','source_corrected_tuned','source_corrected_fixed')]:
    m=pd.read_csv(path)
    for regime,exp in [('tuned',tuned),('fixed',fixed)]:
        s=m[(m.model=='LGBM')&(m.experiment==exp)&(m.block=='2016_2017')]
        aa=float(s[(s.train_version=='A')&(s.score_version=='A')].iloc[0].average_precision)
        bb=float(s[(s.train_version=='B')&(s.score_version=='B')].iloc[0].average_precision)
        metrics.append(dict(scenario=label,regime=regime,block='2016_2017',AA_percent=100*aa,BB_percent=100*bb,delta_pp=100*(bb-aa),source=str(path),source_sha256=digest(path)))
pd.DataFrame(metrics).to_csv(OUT/'table6_firstblock_independent_check.csv',index=False)

pdf=REV/'qa/main_final/Financial_Data_Version_Evaluation.pdf'
page_notes={
    10:'Figure 2 panels, labels and caption visible; no overlap or clipping.',
    11:'Table 4 complete; Figure 3 plot complete. Minor: Figure 3 caption continues for two lines on page 12.',
    12:'Continuation of Figure 3 caption readable; source examples and heading clear; no clipping.',
    13:'Table 5 complete; Figure 4 boxes/axes/caption clear; no overlap.',
    14:'Table 6 complete on one page; footnote visible; no truncation.',
    15:'Discussion text and citations readable; normal paragraph continuation to page 16.',
    16:'Conclusion, availability, AI disclosure and initial references clear; footer unobstructed.',
    17:'References and long URLs readable within margins; thesis type visible.',
    18:'Remaining references/SEC URLs visible; no clipped text or blank extra page.'}
qa={'mode':'Actual visual inspection of each PNG via view_image; not text-only QA','pdf':str(pdf),'pdf_sha256':digest(pdf),
    'pages_inspected':[],'blocking_layout_issues':0,'minor_layout_issues':1}
for n,note in page_notes.items():
    p=pdf.parent/f'page-{n}.png'
    qa['pages_inspected'].append(dict(page=n,path=str(p),sha256=digest(p),finding=note))
(OUT/'visual_review.json').write_text(json.dumps(qa,ensure_ascii=False,indent=2),encoding='utf-8')
(OUT/'author_pending_all_consequential_sources_README.md').write_text(f'''# Consequential source judgments pending author review

This is a consolidated review interface, not a completed human audit. It contains {len(d)} source-component-arm records: 22 Nobilis scale keys, 4 unresolved sign proposals, 21 newly examined targeted display checks, and 12 reused display checks. Repeated source or arm records are not independent observations. Original issuer instance/context/presentation chains remain unauthenticated for every row. All author identity, decision, date, locator, explanation and signature fields are intentionally blank.

The six targeted companies are Rentech, Silver Stream Mining, Gymboree, RTW Retailwinds, RCS Capital and American Healthcare REIT. The table preserves existing exact sources, periods, excerpts, capture hashes and model-stage links. Numerical correction is not proposed for the six mechanism examples. Nobilis display support is not proof of the original XBRL encoding. The four signs stay unresolved; a reader must not infer instance sign from brackets or the debit/credit attribute alone.

`affected_main_features` for numerical keys is linked to the saved source-to-feature trace; for targeted mechanism rows it identifies the examined component, not a separately established causal model effect. All fields were consolidated from previously frozen evidence without new source retrieval or model fitting. Author confirmation requires direct review and an explicit choice; leaving a field blank means pending.
''',encoding='utf-8')
print(json.dumps({'confirmation_rows':len(d),'companies':d.company.unique().tolist(),'firstblock':metrics},ensure_ascii=False,indent=2))

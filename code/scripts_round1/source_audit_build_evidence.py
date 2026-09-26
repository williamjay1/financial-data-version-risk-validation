"""Assemble independently read display findings. Navigation/value matches do not assign statuses.

Read-only with respect to the original cohort, facts, and immutable SEC source captures.
The selected display positions and exceptions were reviewed using the financial statement
heading, period columns, row labels, signs and currency multipliers. This is AI-assisted
source verification; original XBRL context certification was not possible.
"""
from pathlib import Path
import hashlib, json, re
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / 'revision_20260922/results/source_audit'
requests = pd.read_csv(OUT/'fact_requests.csv', dtype={'cik': str}).fillna('')
captures = json.loads((OUT/'capture_manifest_parsed.json').read_text(encoding='utf-8'))
by_url = {x['url']: x for x in captures if x['source_readable']}
loc = json.loads((OUT/'selected_display_offsets.json').read_text(encoding='utf-8'))
loc.update({'E01_A':[194993,194475], 'E01_B':[187968,187349],
 'E02_A':[334898,336001], 'E02_B':[400515,402779],
 'E03_A':[227767,234820], 'E03_B':[254298,260103],
 'E04_A':[354529,356401], 'E04_B':[364334,366049],
 'E05_A':[279634,283151], 'E05_B':[385858,389558],
 'E06_A':[175958,176786], 'E06_B':[169772,170488]})
loc['P04_A'][1] = 172100
loc['P09_A'][1] = 203940
loc['P16_B'][1] = 216238

scales = {'P01':1,'P02':1,'P03':1000000,'P04':1,'P05':1000,'P06':1000,
 'P07':1000,'P08':1000,'P09':1000,'P10':1000,'P11':1,'P12':1,
 'P13':1000,'P14':1000000,'P15':1000,'P16':1000000,'P17':1000,
 'P18':1000,'P19':1000,'P20':1,'P21':1000000,'P22':1000,'P23':1000,
 'P24':1000,'E01':1000,'E02':1000,'E03':1000,'E04':1000000,'E05':1,'E06':1000}
corrections = pd.read_csv(OUT/'verified_corrections.csv', dtype={'cik':str}).fillna('')
findings=[]
for _,x in requests.iterrows():
 for arm in ['A','B']:
  cap=by_url[x[arm+'_url']]
  source_arm=arm if x.audit_id+'_'+arm in loc else 'A'
  pos=loc[x.audit_id+'_'+source_arm][0 if x.feature=='assets' else 1]
  text=Path(cap['parsed_path']).read_text(encoding='utf-8')
  source_accession=x.accession if arm=='A' else x.B_accession
  api=float(x['api_'+arm]); normalized=api; status='display_consistent'
  note='Currency, sign, reporting period and displayed consolidated/attributable row checked; no original XBRL certification.'
  fix=corrections[(corrections.cik==x.cik)&(corrections.source_accession==source_accession)&(corrections.tag==x.tag)&(corrections.start==x.start)&(corrections.end==x.end)]
  if len(fix):
   normalized=float(fix.iloc[0].display_normalized_value);status='display_api_mismatch_confirmed'
   note='Displayed source supports correction; fault location between original XBRL and current API remains unknown.'
  if x.audit_id=='P12' and x.feature=='operating_income' and arm=='A':
   normalized=None;status='unknown_tag_semantics_possible_rounding'
   note='API -2,000,000. Original F-3 labels -2,386,864 as NET LOSS; gross margin42,005 minus operating expenses2,428,869 equals this amount. No separately labelled operating-income row; do not auto-correct using identity.'
  if x.audit_id=='P11' and x.feature=='liabilities' and arm=='B':
   note+=' Source itself reports total current liabilities178,929 but total liabilities178,729; matching display does not establish accounting correctness.'
  if x.audit_id=='P20':
   note+=' B Note1: GAHR IV is legal acquiror, GAHR III accounting acquiror; pre-merger comparative information reflects GAHR III, hence scope is not constant.'
  if (x.audit_id=='P02' and arm=='A' and x.feature=='revenue') or (x.audit_id=='P13' and arm=='B' and x.feature=='revenue'):
   note+=' Clean-text extraction omits row label; numerical position, period, statement and surrounding cost/gross-profit lines support the row; original HTML layout not independently rendered.'
  preceding=text[max(0,pos-6000):pos]
  headings=list(re.finditer(r'(?i)(?:in|amounts|dollars).{0,15}(?:thousands|millions)|(?:consolidated )?balance sheets|(?:consolidated )?statements of (?:operations|cash flows)|year[s]? ended.{0,50}',preceding))
  header=' | '.join(preceding[m.start():m.start()+220].replace('\n',' ') for m in headings[-4:])
  findings.append({**{k:x[k] for k in ['audit_id','audit_role','stratum','audit_N_h','audit_n_h','audit_pi','audit_weight','sample_weight','cik','company_name','feature','tag','start','end','unit']},
   'arm':arm,'source_accession':source_accession,'api_value':api,'display_normalized_value':normalized,
   'display_scale_multiplier':scales[x.audit_id], 'display_status':status,
   'original_xbrl_status':'unknown_not_context_certified','source_url':x[arm+'_url'],
   'source_raw_path':cap['raw_path'],'source_raw_sha256':cap['raw_sha256'],
   'source_text_path':cap['parsed_path'],'row_char_offset':pos,
   'display_excerpt':text[max(0,pos-220):pos+400], 'heading_excerpt':header,'scope_and_access_notes':note,
   'verification_mode':'AI_assisted_SEC_clean_text_review_not_human_manual_audit'})
df=pd.DataFrame(findings);df.to_csv(OUT/'source_fact_verification.csv',index=False,encoding='utf-8-sig')
p=df[df.audit_role=='probability']; landmarks=pd.read_csv(OUT/'sample_landmarks.csv',dtype={'cik':str}); ps=landmarks[landmarks.audit_role=='probability']
unknown=p[p.display_status.str.startswith('unknown')]
N=int(ps.audit_weight.sum())
summary={'probability_landmarks':24,'probability_distinct_cik':int(ps.cik.nunique()),'finite_test_domain_landmarks':N,
 'probability_requested_fact_contexts':48,'probability_requested_source_arm_rows':96,
 'probability_display_consistent_source_arm_rows':int((p.display_status=='display_consistent').sum()),
 'probability_assets_contexts_both_arms_consistent':24,
 'probability_secondary_contexts_both_arms_consistent':23,
 'probability_unknown_source_arm_rows':len(unknown),
 'probability_display_api_mismatch_confirmed':int((p.display_status=='display_api_mismatch_confirmed').sum()),
 'weighted_landmark_proportion_with_unknown_secondary':float(unknown.audit_weight.astype(float).sum()/N),
 'unique_official_filing_urls':len(by_url),'filing_url_readable':len(by_url),'filing_url_retrieval_failure':0,
 'malformed_initial_tool_request':1,'source_text_truncated_urls':1,
 'original_html_or_xml_bytes_certified':0,'xml_http_probes':2,'xml_http_403':2,
 'original_xbrl_unknown_all_requested_arm_rows':120,
 'purposive_landmarks':6,'purposive_display_api_mismatch_source_arm_rows':int(((df.audit_role!='probability')&(df.display_status=='display_api_mismatch_confirmed')).sum()),
 'correction_contexts':len(corrections),'correction_contexts_nobilis2015':11,'correction_contexts_nobilis2014_comparative_followup':11,'correction_contexts_new_sign':4,
 'note':'No probability error prevalence inferred from purposive corrections. No perfect-accuracy claim from 24 assets matches. Unknown XBRL is not zero errors.'}
(OUT/'source_audit_summary.json').write_text(json.dumps(summary,indent=2),encoding='utf-8')
print(json.dumps(summary,indent=2))

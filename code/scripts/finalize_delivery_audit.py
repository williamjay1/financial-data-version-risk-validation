"""Record completed human-visible page inspections and bind delivery to final artifacts.

This records the actual root/agent inspections; rerunning does not inspect new pages.
It refuses to apply the recorded inspection to a changed manuscript.
"""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_DOCX = 'bb394ce29bb8d2f8680ce787cac5e8761c3904274e527f88742f0d4b6b60dd11'
EXPECTED_MARKDOWN = '4d6abbb6ec1529ed161a9fc8db5e454504ea5954f8ef945db43a3b30a0b39bf8'

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def write(name, obj):
    (ROOT/'results'/name).write_text(json.dumps(obj, indent=2, ensure_ascii=False), encoding='utf-8')

def main():
    docx = ROOT/'manuscript/Financial_Vintage_Registry_Prediction_Manuscript.docx'
    md = ROOT/'manuscript/manuscript.md'
    render = ROOT/'temp/word_qa_final'
    pdf = render/'Financial_Vintage_Registry_Prediction_Manuscript.pdf'
    assert sha(docx) == EXPECTED_DOCX
    assert sha(md) == EXPECTED_MARKDOWN
    part1 = json.loads((ROOT/'results/word_visual_qa_part1.json').read_text(encoding='utf-8-sig'))
    assert part1['status'] == 'PASS' and part1['pages_reviewed'] == list(range(1,11))
    assert part1['document']['sha256'] == sha(docx)
    assert part1['pdf']['sha256'] == sha(pdf)
    assert len(list(render.glob('page-*.png'))) == 20
    observations = {
        11: 'Source examples and section 4.3 readable; no clipping. White space permits the next complete main table.',
        12: 'Table 3 is complete with its explanatory note; prose readable and no split row.',
        13: 'Table 4 and Figure 3 readable, caption on same page; original-resolution interval labels checked.',
        14: 'Table 5 and note on the same page; discussion heading followed by substantive text.',
        15: 'Discussion and limitations readable without clipping or overlapping text.',
        16: 'Conclusion, availability, actual AI-use statement and Appendix A opening readable.',
        17: 'Table A1 complete and note readable. Long Table B1 begins with title and rows; continuation repeats header.',
        18: 'Table B1 continuation and note readable. Long Table B2 has intact rows; continues with repeated header.',
        19: 'Table B2 final row and note intact. References readable without clipping or overlap.',
        20: 'Remaining references and DOI/URL strings readable; SEC institution names and arXiv preprint status correct.'
    }
    now = datetime.now(timezone.utc).isoformat()
    part2 = {
        'status':'PASS', 'reviewed_utc':now, 'reviewer':'root',
        'scope':'Final Word pages 11 through 20 individually opened and visually inspected, with original-resolution checks',
        'pages_reviewed':list(range(11,21)), 'document_total_pages':20,
        'document':{'path':str(docx),'sha256':sha(docx)},
        'pdf':{'path':str(pdf),'sha256':sha(pdf)},
        'pages':[{'page':n,'path':str(render/f'page-{n}.png'),
                  'sha256':sha(render/f'page-{n}.png'),'visually_opened':True,
                  'status':'PASS','observations':observations[n]} for n in range(11,21)],
        'blocking_layout_defects':0,
        'nonblocking_observations':['Long appendix tables flow across pages with repeated headers; no split cell or lost row.',
                                    'Some white space retained to keep short main tables and notes together.'],
        'limitations':['Inspection records apply to these exact artifact hashes, not future regenerated files.']
    }
    write('word_visual_qa_part2.json',part2)
    build = json.loads((ROOT/'results/manuscript_build.json').read_text(encoding='utf-8'))
    build.update(visual_qa='PASS_ALL_20_PAGES', rendered_pages=20, docx_sha256=sha(docx),
                 visual_qa_records=['word_visual_qa_part1.json','word_visual_qa_part2.json'])
    write('manuscript_build.json',build)
    final = {
        'completed_utc':now, 'manuscript_stage':'GO_COMPLETE_RESEARCH_MANUSCRIPT',
        'submission_stage':'CONDITIONAL_NOT_SUBMITTED',
        'manuscript':str(docx), 'docx_sha256':sha(docx), 'markdown_sha256':sha(md),
        'rendered_pages':20, 'tables':8, 'figures':3, 'cited_references':33,
        'main_model_independent_checks':297, 'manuscript_numeric_checks':310,
        'final_limited_rechecks':7, 'visual_qa':'PASS_ALL_20_PAGES',
        'interpretation_review':'No blocking factual/citation/overclaim issue; study limitations retained',
        'remaining_submission_work':['Author metadata and accurate declarations',
            'Final journal selection, current policy check and venue-specific formatting',
            'Appropriate public code/data sharing arrangements if required'],
        'key_boundaries':['Original-accession API reconstruction is not a historical API snapshot',
            'Outcome is the first directly linked registry event, not all bankruptcies',
            'Sparse early tuning and validation events',
            'Intervals condition on fitted models and registry cases',
            'Transition-report sensitivity reverses the last-block AP contrast'],
        'external_actions':{'journal_submission':False,'public_upload':False,'contacted_others':False}
    }
    write('final_delivery_audit.json',final)
    print(json.dumps(final,ensure_ascii=False))

if __name__ == '__main__':
    main()

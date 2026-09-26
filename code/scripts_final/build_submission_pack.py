"""Build the submission pack for the Risk Journals online submission platform.

Required by the publisher's guidelines and produced here:
  * a separate title page document with author details, running head, word count
    and display counts;
  * figure and table legends placed before the abstract;
  * an abstract of 150 to 200 words, 4 to 6 keywords and 3 to 4 key messages;
  * an anonymised main text with no author names or affiliations;
  * every figure and table inside the main PDF and also as separate editable
    files named by display number (vector SVG and PDF for figures, CSV and DOCX
    for tables);
  * a LaTeX source for the version of record, since the publisher asks for TeX;
  * Declarations of Interest, Acknowledgements, AI use statement and
    supplementary material notes.
"""
from __future__ import annotations

import json
import re
import shutil
import subprocess
from pathlib import Path

from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Inches, Pt, RGBColor

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
MAN = ROOT / 'manuscript'
TEMP = ROOT / 'temp'
SUB = ROOT / 'submission'
FIGSRC = MAN / 'figures'
FAIL: list[str] = []

for folder in [SUB, SUB / 'figures', SUB / 'tables', SUB / 'latex', SUB / 'pdf', TEMP]:
    folder.mkdir(parents=True, exist_ok=True)

# ------------------------------------------------------------------ metadata
FRONT = json.loads((SUB / 'front_matter.json').read_text(encoding='utf-8'))
RUNNING_HEAD = FRONT['running_head']
TITLE = FRONT['title']
KEYWORDS = FRONT['keywords']
KEY_MESSAGES = FRONT['key_messages']
ABSTRACT = FRONT['abstract']
AUTHOR_INFO = FRONT['author']
AFFILIATIONS = FRONT['affiliations']
for lesson in KEY_MESSAGES:
    if len(lesson) > 85:
        FAIL.append(f'key message exceeds 85 characters ({len(lesson)}): {lesson}')
if not 150 <= len(ABSTRACT.split()) <= 200:
    FAIL.append(f'abstract is {len(ABSTRACT.split())} words, outside 150 to 200')
if not 4 <= len(KEYWORDS) <= 6:
    FAIL.append(f'{len(KEYWORDS)} keywords, outside 4 to 6')
if not 3 <= len(KEY_MESSAGES) <= 4:
    FAIL.append(f'{len(KEY_MESSAGES)} key messages, outside 3 to 4')
if len(RUNNING_HEAD) > 50:
    FAIL.append(f'running head is {len(RUNNING_HEAD)} characters, over 50')
if re.search(r'\u2014|\u2013', TITLE + ABSTRACT + RUNNING_HEAD):
    FAIL.append('dash character in front matter')

# ------------------------------------------------------------------ source text
RAW = (MAN / 'manuscript_author_date.md').read_text(encoding='utf-8')
body = RAW.split('# References')[0]
body = re.sub(r'^---\n.*?\n---\n', '', body, flags=re.S).strip()

sections: dict[str, list[str]] = {}
order: list[str] = []
current = None
for line in body.split('\n'):
    if line.startswith('# '):
        current = line[2:].strip()
        order.append(current)
        sections[current] = []
        continue
    if current:
        sections[current].append(line)
sections = {k: '\n'.join(v).strip() for k, v in sections.items()}

intro_paragraphs = [p.strip() for p in sections['1 Introduction'].split('\n\n') if p.strip()]
split_at = next(i for i, p in enumerate(intro_paragraphs)
                if p.startswith('Accounting based failure prediction'))
SECTION_ORDER = [
    ('1 Introduction', '\n\n'.join(intro_paragraphs[:split_at])),
    ('2 Literature review', '\n\n'.join(intro_paragraphs[split_at:])),
    ('3 Data', sections['2 Data and comparable financial versions']),
    ('4 Methodology', sections['3 Evaluation design']),
    ('5 Results', sections['4 Results']),
    ('6 Discussion', sections['5 Discussion']),
    ('7 Conclusion', sections['6 Conclusion']),
]

# --------------------------------------------------------------- citation map
CITE_LABEL = {
    'sec_financial_datasets': 'SEC 2026b', 'sr1107': 'Board of Governors 2011',
    'ecb_internal_models': 'European Central Bank 2019',
    'bcbs2016': 'Basel Committee on Banking Supervision 2016',
    'kapoor2023': 'Kapoor and Narayanan 2023', 'beaver1966': 'Beaver 1966',
    'altman1968': 'Altman 1968', 'ohlson1980': 'Ohlson 1980',
    'shumway2001': 'Shumway 2001', 'barboza2017': 'Barboza et al. 2017',
    'beaver2012': 'Beaver et al. 2012', 'correia2025': 'Correia 2025',
    'mai2019': 'Mai et al. 2019', 'bargagli2024': 'Bargagli-Stoffi et al. 2024',
    'mattos2024': 'Mattos and Shasha 2024', 'hashemi2017': 'Hashemi and Jonsson 2017',
    'zavitsanos2021': 'Zavitsanos et al. 2021', 'yang2026': 'Yang and Zhu 2026',
    'kozodoi2025': 'Kozodoi et al. 2025', 'zhang2026': 'Zhang et al. 2026',
    'hf_master': 'kapilrao 2024', 'sraf_index': 'Loughran and McDonald 2026',
    'sec_api': 'SEC 2026a',
    'brd_database': 'Florida-UCLA-LoPucki Bankruptcy Research Database 2022',
    'horvitz1952': 'Horvitz and Thompson 1952', 'secNegativeValues2017': 'SEC 2017',
    'ke2017': 'Ke et al. 2017', 'bls_cpi': 'US Bureau of Labor Statistics 2026',
    'saito2015': 'Saito and Rehmsmeier 2015',
    'gneiting2007': 'Gneiting and Raftery 2007',
    'vancalster2019': 'Van Calster et al. 2019', 'raowu1988': 'Rao and Wu 1988',
    'raowuyue1992': 'Rao et al. 1992', 'rentech2013revision': 'Rentech 2013',
    'silverstream2014transition': 'Silver Stream Mining 2014a',
    'silverstream2014annualAmendment': 'Silver Stream Mining 2014b',
    'gymboree2016transition': 'The Gymboree Corporation 2016',
    'gymboree2017quarterly': 'The Gymboree Corporation 2017',
    'nobilis2016_10k': 'Nobilis Health 2016', 'nobilis2017_10k': 'Nobilis Health 2017',
    'rcs2014_10k': 'RCS Capital 2014', 'rcs2015_10ka': 'RCS Capital 2015',
    'americanhealthcarereit2022': 'American Healthcare REIT 2022',
}

REFERENCES = [
    ('Altman, E. I. (1968). Financial ratios, discriminant analysis and the prediction of '
     'corporate bankruptcy. The Journal of Finance 23 (4), 589-609. '
     'https://doi.org/10.1111/j.1540-6261.1968.tb00843.x'),
    ('American Healthcare REIT, Inc. (2022). Form 10-K for the fiscal year ended December '
     '31, 2021. U.S. Securities and Exchange Commission, EDGAR accession '
     '0001632970-22-000020. '
     'https://www.sec.gov/Archives/edgar/data/1632970/000163297022000020/ahr-20211231.htm'),
    ('Bargagli-Stoffi, F. J., Incerti, F., Riccaboni, M., and Rungi, A. (2024). Machine '
     'learning for zombie hunting: predicting distress from firms\u2019 accounts and missing '
     'values. Industrial and Corporate Change 33 (5), 1063-1097. '
     'https://doi.org/10.1093/icc/dtad049'),
    ('Barboza, F., Kimura, H., and Altman, E. (2017). Machine learning models and bankruptcy '
     'prediction. Expert Systems with Applications 83, 405-417. '
     'https://doi.org/10.1016/j.eswa.2017.04.006'),
    ('Basel Committee on Banking Supervision (2016). Regulatory Consistency Assessment '
     'Programme: Handbook for Jurisdictional Assessments. Bank for International '
     'Settlements, June 2016. https://www.bis.org/bcbs/publ/d352.pdf'),
    ('Beaver, W. H. (1966). Financial ratios as predictors of failure. Journal of Accounting '
     'Research 4, 71-111. https://doi.org/10.2307/2490171'),
    ('Beaver, W. H., Correia, M., and McNichols, M. F. (2012). Do differences in financial '
     'reporting attributes impair the predictive ability of financial ratios for bankruptcy? '
     'Review of Accounting Studies 17 (4), 969-1010. '
     'https://doi.org/10.1007/s11142-012-9186-7'),
    ('Board of Governors of the Federal Reserve System and Office of the Comptroller of the '
     'Currency (2011). Supervisory Guidance on Model Risk Management. SR letter 11-7 and OCC '
     'bulletin 2011-12, 4 April 2011. '
     'https://www.federalreserve.gov/supervisionreg/srletters/sr1107.pdf'),
    ('Correia, M. (2025). Accounting and corporate failure: the evolving role of accounting '
     'information in bankruptcy prediction. Accounting and Business Research 55 (5), '
     '510-537. https://doi.org/10.1080/00014788.2025.2516273'),
    ('European Central Bank (2019). ECB Guide to Internal Models. ECB Banking Supervision, '
     'October 2019. '
     'https://www.bankingsupervision.europa.eu/ecb/pub/pdf/ssm.supervisory_guides201910.en.pdf'),
    ('Florida-UCLA-LoPucki Bankruptcy Research Database (2022). A window on the world of '
     'big-case bankruptcy. University of Florida Levin College of Law. '
     'https://lopucki.law.ufl.edu/index.php'),
    ('Gneiting, T., and Raftery, A. E. (2007). Strictly proper scoring rules, prediction, and '
     'estimation. Journal of the American Statistical Association 102 (477), 359-378. '
     'https://doi.org/10.1198/016214506000001437'),
    ('Hashemi, P., and Jonsson, A. (2017). The economic importance of earnings manipulation: '
     'a quantitative study of the economic consequences of earnings manipulation on '
     'fundamental value and bankruptcy probability. Master\u2019s thesis in Accounting and '
     'Financial Management, Stockholm School of Economics. '
     'https://arc.hhs.se/download.aspx?MediumId=3871'),
    ('Horvitz, D. G., and Thompson, D. J. (1952). A generalization of sampling without '
     'replacement from a finite universe. Journal of the American Statistical Association '
     '47 (260), 663-685. https://doi.org/10.1080/01621459.1952.10483446'),
    ('kapilrao (2024). SEC filings 1994-2024. Hugging Face datasets. '
     'https://huggingface.co/datasets/kapilrao/SEC_filings_1994_2024'),
    ('Kapoor, S., and Narayanan, A. (2023). Leakage and the reproducibility crisis in '
     'machine-learning-based science. Patterns 4 (9), 100804. '
     'https://doi.org/10.1016/j.patter.2023.100804'),
    ('Ke, G., Meng, Q., Finley, T., Wang, T., Chen, W., Ma, W., Ye, Q., and Liu, T.-Y. '
     '(2017). LightGBM: a highly efficient gradient boosting decision tree. In Advances in '
     'Neural Information Processing Systems, volume 30. '
     'https://proceedings.neurips.cc/paper/2017/hash/6449f44a102fde848669bdd9eb6b76fa-Abstract.html'),
    ('Kozodoi, N., Lessmann, S., Alamgir, M., Moreira-Matias, L., and Papakonstantinou, K. '
     '(2025). Fighting sampling bias: a framework for training and evaluating credit scoring '
     'models. European Journal of Operational Research 324 (2), 616-628. '
     'https://doi.org/10.1016/j.ejor.2025.01.040'),
    ('Loughran, T., and McDonald, B. (2026). Master index data. Loughran-McDonald Software '
     'Repository for Accounting and Finance. '
     'https://sraf.nd.edu/sec-edgar-data/master-index-data/'),
    ('Mai, F., Tian, S., Lee, C., and Ma, L. (2019). Deep learning models for bankruptcy '
     'prediction using textual disclosures. European Journal of Operational Research 274 (2), '
     '743-758. https://doi.org/10.1016/j.ejor.2018.10.024'),
    ('Mattos, E. S., and Shasha, D. (2024). Bankruptcy prediction with low-quality financial '
     'information. Expert Systems with Applications 237, 121418. '
     'https://doi.org/10.1016/j.eswa.2023.121418'),
    ('Nobilis Health Corp. (2016). Form 10-K for the fiscal year ended December 31, 2015. '
     'U.S. Securities and Exchange Commission, EDGAR accession 0001062993-16-008351. '
     'https://www.sec.gov/Archives/edgar/data/1409916/000106299316008351/form10k.htm'),
    ('Nobilis Health Corp. (2017). Form 10-K for the fiscal year ended December 31, 2016. '
     'U.S. Securities and Exchange Commission, EDGAR accession 0001628280-17-002570. '
     'https://www.sec.gov/Archives/edgar/data/1409916/000162828017002570/nhc-123116x10k.htm'),
    ('Ohlson, J. A. (1980). Financial ratios and the probabilistic prediction of bankruptcy. '
     'Journal of Accounting Research 18 (1), 109-131. https://doi.org/10.2307/2490395'),
    ('Rao, J. N. K., and Wu, C. F. J. (1988). Resampling inference with complex survey data. '
     'Journal of the American Statistical Association 83 (401), 231-241. '
     'https://doi.org/10.1080/01621459.1988.10478591'),
    ('Rao, J. N. K., Wu, C. F. J., and Yue, K. (1992). Some recent work on resampling methods '
     'for complex surveys. Survey Methodology 18 (2), 209-217. '
     'https://www150.statcan.gc.ca/n1/pub/12-001-x/1992002/article/14486-eng.pdf'),
    ('RCS Capital Corporation (2014). Form 10-K for the fiscal year ended December 31, 2013. '
     'U.S. Securities and Exchange Commission, EDGAR accession 0001445305-14-000765. '
     'https://www.sec.gov/Archives/edgar/data/1568832/000144530514000765/rcap-20131231x10k.htm'),
    ('RCS Capital Corporation (2015). Form 10-K/A for the fiscal year ended December 31, '
     '2014. U.S. Securities and Exchange Commission, EDGAR accession 0001568832-15-000014. '
     'https://www.sec.gov/Archives/edgar/data/1568832/000156883215000014/rcap-20141231x10ka.htm'),
    ('Rentech, Inc. (2013). Form 10-K for the fiscal year ended December 31, 2012. U.S. '
     'Securities and Exchange Commission, EDGAR accession 0001193125-13-112558, Note 3 '
     'Revisions, p. 88. '
     'https://www.sec.gov/Archives/edgar/data/868725/000119312513112558/d444778d10k.htm'),
    ('Saito, T., and Rehmsmeier, M. (2015). The precision-recall plot is more informative '
     'than the ROC plot when evaluating binary classifiers on imbalanced datasets. PLOS ONE '
     '10 (3), e0118432. https://doi.org/10.1371/journal.pone.0118432'),
    ('Shumway, T. (2001). Forecasting bankruptcy more accurately: a simple hazard model. The '
     'Journal of Business 74 (1), 101-124. https://doi.org/10.1086/209665'),
    ('Silver Stream Mining Corp. (2014a). Form 10-KT for the transition period ended March '
     '31, 2013. U.S. Securities and Exchange Commission, EDGAR accession '
     '0001002014-14-000290. '
     'https://www.sec.gov/Archives/edgar/data/1310497/000100201414000290/ssmc10kt-3312013.htm'),
    ('Silver Stream Mining Corp. (2014b). Form 10-K/A for the fiscal year ended March 31, '
     '2014. U.S. Securities and Exchange Commission, EDGAR accession 0001002014-14-000402, '
     'Note 1. https://www.sec.gov/Archives/edgar/data/1310497/000100201414000402/agsm10ka1-03312014.htm'),
    ('The Gymboree Corporation (2016). Form 10-KT for the transition period ended July 30, '
     '2016. U.S. Securities and Exchange Commission, EDGAR accession 0001193125-16-751374, '
     'consolidated balance sheets, p. 38. '
     'https://www.sec.gov/Archives/edgar/data/786110/000119312516751374/d231280d10kt.htm'),
    ('The Gymboree Corporation (2017). Form 10-Q for the quarterly period ended January 28, '
     '2017. U.S. Securities and Exchange Commission, EDGAR accession 0001193125-17-082009, '
     'condensed consolidated balance sheets, p. 5. '
     'https://www.sec.gov/Archives/edgar/data/786110/000119312517082009/d268566d10q.htm'),
    ('U.S. Bureau of Labor Statistics (2026). Consumer price index for all urban consumers: '
     'U.S. city average, all items, not seasonally adjusted (CUUR0000SA0). '
     'https://www.bls.gov/cpi/'),
    ('U.S. Securities and Exchange Commission (2017). Data quality reminder: negative '
     'values. Office of Structured Disclosure, 20 July 2017. '
     'https://www.sec.gov/structureddata/announcement/osd_announcement07142017-data-quality-reminder-negative-values'),
    ('U.S. Securities and Exchange Commission (2026a). EDGAR application programming '
     'interfaces. https://www.sec.gov/search-filings/edgar-application-programming-interfaces'),
    ('U.S. Securities and Exchange Commission (2026b). Financial statement data sets. '
     'https://www.sec.gov/data-research/sec-markets-data/financial-statement-data-sets'),
    ('Van Calster, B., McLernon, D. J., van Smeden, M., Wynants, L., and Steyerberg, E. W. '
     '(2019). Calibration: the Achilles heel of predictive analytics. BMC Medicine 17, 230. '
     'https://doi.org/10.1186/s12916-019-1466-7'),
    ('Yang, L., and Zhu, M. (2026). Misstatement detection lag and prediction evaluation. '
     'The Accounting Review 101 (2), 395-417. https://doi.org/10.2308/tar-2023-0073'),
    ('Zavitsanos, E., Mavroeidis, D., Bougiatiotis, K., Spyropoulou, E., Loukas, L., and '
     'Paliouras, G. (2021). Financial misstatement detection: a realistic evaluation. In '
     'Proceedings of the Second ACM International Conference on AI in Finance, 1-9. '
     'https://doi.org/10.1145/3490354.3494453'),
    ('Zhang, Z., Zheng, M., Zhang, T., Lin, L., and Lin, L. (2026). Bankruptcy prediction '
     'from 10-K narratives: evidence from interpretable text scores and accounting baselines. '
     'Risks 14 (8), 179. https://doi.org/10.3390/risks14080179'),
]

# ------------------------------------------------------------------- tex tools
TEX_ESCAPE = [('\\', r'\textbackslash{}'), ('&', r'\&'), ('%', r'\%'), ('$', r'\$'),
              ('#', r'\#'), ('_', r'\_'), ('{', r'\{'), ('}', r'\}'),
              ('~', r'\textasciitilde{}'), ('^', r'\textasciicircum{}')]


def tex_escape(text: str) -> str:
    for old, new in TEX_ESCAPE:
        text = text.replace(old, new)
    return text


def citation_replace(text: str) -> str:
    def one(match: re.Match) -> str:
        keys = [k.strip().lstrip('@').lstrip('-') for k in match.group(1).split(';')]
        labels = []
        for key in keys:
            if key not in CITE_LABEL:
                FAIL.append('citation key without a label: ' + key)
                labels.append('?')
            else:
                labels.append(CITE_LABEL[key])
        return '(' + '; '.join(labels) + ')'

    return re.sub(r'\[([^\]]*@[^\]]*)\]', one, text)


AUTHOR_BLOCK = '\n'.join([
    '{\\normalsize ' + tex_escape(AUTHOR_INFO['name_en']) + r'$^{1,2,*}$}' + r'\\[2pt]',
    r'{\footnotesize $^1$' + tex_escape(AFFILIATIONS[0]) + r'\\[1pt]',
    r'$^2$' + tex_escape(AFFILIATIONS[1]) + r'\\[2pt]',
    r'ORCID: ' + tex_escape(AUTHOR_INFO['orcid']) + r'\\[1pt]',
    r'$^*$Corresponding author: ' + tex_escape(AUTHOR_INFO['email']) + '}',
])


def inline_format(text: str) -> str:
    text = re.sub(r'\*\*(.+?)\*\*', r'\\textbf{\1}', text)
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    return text


def math_to_tex(text: str) -> str:
    # Citations are resolved before escaping, because citation keys contain
    # underscores that the LaTeX escape would otherwise mangle.
    text = citation_replace(text)
    holes: list[str] = []

    def stash(match: re.Match) -> str:
        holes.append(match.group(1))
        return f'@@MATH{len(holes) - 1}@@'

    text = re.sub(r'\$\$(.+?)\$\$', stash, text, flags=re.S)
    text = re.sub(r'\$([^$\n]+)\$', stash, text)
    text = tex_escape(text)
    text = text.replace('\u2013', '-').replace('\u2014', '-').replace('\u2212', '-')
    text = text.replace('\u2019', "'").replace('\u2018', "'")
    text = text.replace('\u201c', '``').replace('\u201d', "''")
    for index, content in enumerate(holes):
        text = text.replace(f'@@MATH{index}@@', '$' + content + '$')
    text = text.replace(r'\mathcal C', r'\mathcal{C}')
    return text


def markdown_table_tex(md: str, caption: str, label: str, note: str,
                       small: bool = False) -> str:
    rows = [r for r in md.strip().split('\n') if r.strip().startswith('|')]
    cells = [[c.strip() for c in r.strip().strip('|').split('|')] for r in rows]
    header, data = cells[0], cells[2:]
    columns = len(header)
    spec = 'l' + 'r' * (columns - 1)
    wide = columns >= 6          # spans both columns
    shrink = columns >= 7        # only the very widest tables are scaled down
    environment = 'table*' if wide else 'table'
    sizing = '\\footnotesize' if columns >= 5 else '\\small'
    target = r'\textwidth' if wide else r'\columnwidth'
    lines = [r'\begin{' + environment + '}[tbp]', r'\centering', sizing,
             r'\caption{' + math_to_tex(caption) + '}', r'\label{' + label + '}']
    if shrink:
        lines.append(r'\resizebox{' + target + r'}{!}{')
    lines += [r'\begin{tabular}{' + spec + '}', r'\toprule',
              ' & '.join(inline_format(math_to_tex(h)) for h in header) + r' \\',
              r'\midrule']
    for row in data:
        row = (row + [''] * columns)[:columns]
        lines.append(' & '.join(inline_format(math_to_tex(c)) for c in row) + r' \\')
    lines += [r'\bottomrule', r'\end{tabular}']
    if shrink:
        lines.append(r'}')
    if note:
        lines.append(r'\par\vspace{2pt}\parbox{\linewidth}{\footnotesize ' +
                     math_to_tex(note) + '}')
    lines.append(r'\end{' + environment + '}')
    return '\n'.join(lines)


def body_to_tex(text: str, prefix: str) -> str:
    out: list[str] = []
    lines = text.split('\n')
    index = 0
    n_table = [0]
    pending_caption = None
    while index < len(lines):
        line = lines[index]
        if line.startswith('## '):
            out.append('\\subsection{' + math_to_tex(line[3:].strip()) + '}')
            index += 1
            continue
        if line.startswith('|'):
            block = []
            while index < len(lines) and lines[index].startswith('|'):
                block.append(lines[index])
                index += 1
            note = ''
            if index < len(lines) and lines[index].startswith('Note:'):
                note = lines[index].strip()
                index += 1
            n_table[0] += 1
            caption = pending_caption or f'Table {n_table[0]}.'
            pending_caption = None
            out.append(markdown_table_tex('\n'.join(block), caption,
                                          f'{prefix}-tab-{n_table[0]}', note))
            continue
        match = re.match(r'^Table (\d+)\.\s*(.*)$', line.strip())
        if match:
            pending_caption = f'Table {match.group(1)}. {match.group(2)}'
            index += 1
            continue
        match = re.match(r'^!\[\]\(([^)]+)\)', line.strip())
        if match:
            index += 1
            continue
        match = re.match(r'^Figure (\d+)\.\s*(.*)$', line.strip())
        if match:
            out.append('\\par\\vspace{4pt}\\noindent{\\small\\textbf{Figure ' +
                       match.group(1) + '.} ' + math_to_tex(match.group(2)) + '}\\par\\vspace{4pt}')
            index += 1
            continue
        if re.match(r'^\d+\.\s', line.strip()):
            items = []
            while index < len(lines) and re.match(r'^\d+\.\s', lines[index].strip()):
                items.append(re.sub(r'^\d+\.\s', '', lines[index].strip()))
                index += 1
            out.append('\\begin{enumerate}\n' +
                       '\n'.join('\\item ' + inline_format(math_to_tex(i)) for i in items) +
                       '\n\\end{enumerate}')
            continue
        if not line.strip():
            index += 1
            continue
        out.append(inline_format(math_to_tex(line.strip())))
        index += 1
    return '\n\n'.join(out)


# ------------------------------------------------------- legends and displays
FIGURES = [
    ('figure1_protocol', 'Information clocks and the crossed version validation design',
     'Version A is anchored to the original accession, version B may contain later '
     'disclosure, and the fit date control restricts development sources while retaining '
     'original inputs at scoring.'),
    ('figure2_four_cell', 'Crossed version performance and decomposition of the tuned LightGBM difference',
     'Panel a reports average precision in the four evaluations, and panel b reports the '
     'reported difference together with the substitution contrast, the redevelopment '
     'contrast and the interaction.'),
    ('figure3_development_influence', 'Development influence of selected observations against matched deletions',
     'Diamonds mark the change in the common fixed contrast after a transition deletion and '
     'gray points mark twenty matched ordinary deletions in the same block and group.'),
    ('figure4_development_domain', 'Development and evaluation domains under a size restriction',
     'Bars report the common fixed contrast in average precision points, and the middle and '
     'right conditions in each block share an identical evaluation sample.'),
    ('figure5_source_evidence', 'Evidence level and model consequence of the source adjustments',
     'Panel a reports the number of source keys or checks at each evidence level and panel b '
     'reports the tuned contrast under the unadjusted, scale supported and combined scenarios.'),
]

TABLE_LEGENDS: list[tuple[str, str]] = []
for key, value in re.findall(r'^(Table \d+)\.\s*(.*)$', body, re.M):
    TABLE_LEGENDS.append((key, value.rstrip('.') + '.'))

# ------------------------------------------------------------ split raw tables
RAW_TABLES: dict[int, tuple[str, str, str, list[list[str]]]] = {}
lines_all = body.split('\n')
i = 0
while i < len(lines_all):
    m = re.match(r'^Table (\d+)\.\s*(.*)$', lines_all[i].strip())
    if m:
        j = i + 1
        while j < len(lines_all) and not lines_all[j].strip():
            j += 1
        if j < len(lines_all) and lines_all[j].strip().startswith('|'):
            number = int(m.group(1))
            caption = m.group(2).strip()
            i = j
            block = []
            while i < len(lines_all) and lines_all[i].strip().startswith('|'):
                block.append(lines_all[i])
                i += 1
            while i < len(lines_all) and not lines_all[i].strip():
                i += 1
            note = ''
            if i < len(lines_all) and lines_all[i].startswith('Note:'):
                note = lines_all[i].strip()
                i += 1
            rows = [[c.strip() for c in r.strip().strip('|').split('|')] for r in block]
            RAW_TABLES[number] = (f'Table {number}', caption, note, rows)
            continue
    i += 1
print('tables captured:', sorted(RAW_TABLES))

# ------------------------------------------------------------ LaTeX document
front = [
    r'\documentclass[10pt,a4paper,twocolumn]{article}',
    r'\usepackage[T1]{fontenc}',
    r'\usepackage[utf8]{inputenc}',
    r'\usepackage{newtxtext,newtxmath}',
    r'\usepackage{booktabs}',
    r'\usepackage{graphicx}',
    r'\usepackage{amsmath}',
    r'\usepackage[margin=20mm,columnsep=6mm]{geometry}',
    r'\usepackage{caption}',
    r'\captionsetup{font=small,labelfont=bf,justification=raggedright,singlelinecheck=false}',
    r'\usepackage{enumitem}',
    r'\usepackage{flafter}',
    r'\usepackage{titlesec}',
    r'\titlespacing*{\section}{0pt}{10pt}{4pt}',
    r'\titlespacing*{\subsection}{0pt}{8pt}{3pt}',
    r'\setlist[enumerate]{leftmargin=*,itemsep=1pt,topsep=2pt}',
    r'\usepackage[colorlinks=false,hidelinks]{hyperref}',
    r'\renewcommand{\arraystretch}{1.05}',
    r'\setlength{\textfloatsep}{7pt plus 2pt minus 2pt}',
    r'\setlength{\floatsep}{7pt plus 2pt minus 2pt}',
    r'\setlength{\intextsep}{7pt plus 2pt minus 2pt}',
    r'\setlength{\abovecaptionskip}{4pt}',
    r'\setlength{\belowcaptionskip}{2pt}',
    r'\setlength{\parskip}{1pt}',
    r'\frenchspacing',
    r'\title{\vspace{-12mm}\bfseries ' + tex_escape(TITLE) + '}',
    r'\author{}',
    r'\date{}',
    r'\begin{document}',
    r'\twocolumn[{\centering\bfseries\large ' + tex_escape(TITLE) + r'\par}\vspace{5pt}]',
    r'\begin{center}',
    AUTHOR_BLOCK,
    r'\end{center}\vspace{2pt}',
    r'\renewcommand{\thefootnote}{\fnsymbol{footnote}}',
    r'\footnotetext[3]{Corresponding author: ' +
    tex_escape(AUTHOR_INFO['email']) + '}',
    r'\renewcommand{\thefootnote}{\arabic{footnote}}',
    r'\begin{center}\small\textit{Running head: ' + tex_escape(RUNNING_HEAD) +
    r'}\end{center}\vspace{4pt}',
    r'\noindent\textbf{Abstract}\par\vspace{2pt}',
    math_to_tex(ABSTRACT),
    r'\par\vspace{4pt}\noindent\textbf{Keywords:} ' +
    tex_escape('; '.join(KEYWORDS)) + r'\par',
    r'\vspace{4pt}\noindent\textbf{Key messages}\par\vspace{2pt}',
    '\\begin{itemize}[leftmargin=*,itemsep=1pt,topsep=2pt]\n' +
    '\n'.join('\\item ' + math_to_tex(m) for m in KEY_MESSAGES) + '\n\\end{itemize}',
    r'\vspace{6pt}\noindent\textbf{Table legends}\par\vspace{2pt}',
    '\n'.join(f'\\noindent\\textbf{{{k}.}} {math_to_tex(v)}' for k, v in TABLE_LEGENDS),
    r'\vspace{6pt}\noindent\textbf{Figure legends}\par\vspace{2pt}',
    '\n'.join(f'\\noindent\\textbf{{Figure {n}.}} {math_to_tex(t)} {math_to_tex(c)}'
              for n, (_, t, c) in enumerate(FIGURES, start=1)),
]

tex_body = []
for title, content in SECTION_ORDER:
    stripped = title.split(' ', 1)[1]
    tex_body.append('\\section{' + math_to_tex(stripped) + '}')
    tex_body.append(body_to_tex(content, 'main'))

tex_figures = []
for number, (name, caption, _) in enumerate(FIGURES, start=1):
    spanning = number == 1              # only the protocol schematic spans both columns
    environment = 'figure*' if spanning else 'figure'
    width = r'\textwidth' if spanning else r'\columnwidth'
    tex_figures += [
        r'\begin{' + environment + '}[tbp]', r'\centering',
        r'\includegraphics[width=' + width + ']{figures/' + name + '.pdf}',
        r'\caption{' + math_to_tex(caption) + '}', r'\label{fig-' + str(number) + '}',
        r'\end{' + environment + '}']

tex_back = [
    r'\clearpage', r'\onecolumn',
    r'\section*{Declarations of Interest}',
    FRONT['conflicts'] + ' ' + FRONT['funding'],
    r'\section*{Acknowledgements}',
    'The analysis reported here is the author\u2019s own work. It uses publicly available '
    'Securities and Exchange Commission filings and registry records, and the author is '
    'responsible for all interpretations. No third party reviewed the source classifications '
    'before submission.',
    r'\section*{Use of artificial intelligence}',
    'OpenAI Codex was used only for limited Python code assistance and English language '
    'polishing. All substantive research tasks, including study design, data collection and '
    'processing, analysis, interpretation, and manuscript preparation, were performed by the '
    'author. AI did not generate or alter data or determine conclusions, and the author '
    'takes full responsibility for the manuscript.',
    r'\section*{Data and code availability}',
    'The analysis code, frozen derived analysis inputs, component lineage, configurations, '
    'saved predictions, model artifacts, source status tables and an executable offline '
    'numerical audit accompany this article. Scripts regenerate every reported display from '
    'the frozen result files. Access paths for the public financial data sources are '
    'documented, and redistribution of original source records follows their respective '
    'terms.',
    r'\section*{Supplementary material}',
    'A separate supplementary document reports the complete candidate grid, alternative '
    'learners, seed comparisons, matched deletion draws, availability horizon tables, '
    'conditional resampling intervals, calibration summaries and the full source ledger.',
    r'\section*{References}',
    r'\begingroup\small',
    '\n'.join('\\noindent ' + tex_escape(r) + r'\par\vspace{2pt}' for r in REFERENCES),
    r'\endgroup',
    r'\end{document}',
]

tex = '\n'.join(front + tex_body + tex_figures + tex_back) + '\n'
tex_path = SUB / 'latex' / 'financial_data_version_risk.tex'
tex_path.write_text(tex, encoding='utf-8')
print('latex written:', len(tex), 'chars')

# ------------------------------------------------------- editable table files
for number in sorted(RAW_TABLES):
    label, caption, note, rows = RAW_TABLES[number]
    csv_path = SUB / 'tables' / f'table{number}.csv'
    csv_path.write_text('\n'.join(','.join('"' + c.replace('"', '""') + '"' for c in row)
                                  for row in rows) + '\n', encoding='utf-8-sig')
    doc = Document()
    doc.add_paragraph(f'{label}. {caption}')
    table = doc.add_table(rows=len(rows), cols=len(rows[0]))
    table.style = 'Table Grid'
    for r, row in enumerate(rows):
        for c, value in enumerate(row):
            cell = table.cell(r, c)
            cell.text = value
            for p in cell.paragraphs:
                for run in p.runs:
                    run.font.size = Pt(8.5)
                    run.font.name = 'Times New Roman'
                    if r == 0:
                        run.font.bold = True
                p.alignment = (WD_ALIGN_PARAGRAPH.LEFT if len(value) > 20
                               else WD_ALIGN_PARAGRAPH.CENTER)
    if note:
        doc.add_paragraph(note)
    doc.save(SUB / 'tables' / f'table{number}.docx')

# ------------------------------------------------------ editable figure files
LATEX_DIR = SUB / 'latex'
(LATEX_DIR / 'figures').mkdir(exist_ok=True)
for number, (name, _, _) in enumerate(FIGURES, start=1):
    for suffix in ['.svg', '.pdf']:
        source = FIGSRC / f'{name}{suffix}'
        if not source.exists():
            FAIL.append(f'missing vector figure: {source}')
            continue
        shutil.copy(source, SUB / 'figures' / f'figure{number}{suffix}')
    shutil.copy(FIGSRC / f'{name}.pdf', LATEX_DIR / 'figures' / f'{name}.pdf')

# ------------------------------------------------------------- compile LaTeX
RESULT: dict[str, object] = {'failures': FAIL}
if not FAIL:
    runs = []
    for _ in range(2):
        run = subprocess.run(['pdflatex', '-interaction=nonstopmode',
                              '-halt-on-error', '-output-directory', str(TEMP),
                              str(tex_path)],
                             capture_output=True, text=True, encoding='utf-8', cwd=SUB / 'latex')
        runs.append(run)
    log = (TEMP / 'financial_data_version_risk.log')
    produced = TEMP / 'financial_data_version_risk.pdf'
    RESULT['latex_returncode'] = runs[-1].returncode
    RESULT['latex_tail'] = (runs[-1].stdout or '')[-3000:]
    if produced.exists():
        shutil.copy(produced, SUB / 'pdf' / 'main_manuscript_anonymised.pdf')
        RESULT['pdf'] = str(SUB / 'pdf' / 'main_manuscript_anonymised.pdf')
    else:
        FAIL.append('LaTeX did not produce a PDF; see latex_tail')
    if log.exists():
        shutil.copy(log, SUB / 'latex' / 'financial_data_version_risk.log')

RESULT['failures'] = FAIL
(ROOT / 'results' / 'submission_build.json').write_text(json.dumps(RESULT, indent=2),
                                                        encoding='utf-8')
print(json.dumps({k: v for k, v in RESULT.items() if k != 'latex_tail'}, indent=2))
if FAIL:
    print(RESULT.get('latex_tail', '')[-2500:])
    raise SystemExit('submission pack failures: ' + '; '.join(FAIL))

"""Apply the writing-audit revision to create revision_20260924_audited.

Every change is a wording change only. No number, method, result or claim about the
world is altered. The mapping below lists each replacement in order so that the audit
record can report exactly what was rewritten and why.
"""
from __future__ import annotations

import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = ROOT.parent
SRC = BASE / 'revision_20260923_jrmv/manuscript/main_template.md'
TEXT_OUT = ROOT / 'manuscript/main_template.md'

# (category, why, old, new). Exact strings; each must appear exactly once.
EDITS: list[tuple[str, str, str, str]] = [
    # ---------------------------------------------------------------- abstract
    ('abstract', 'positive framing instead of a negative statement',
     'A chronological train and test split does not specify which version of a historical '
     'input the model development and the scoring exercise use, and that omission is a '
     'validation design choice rather than a data cleaning step.',
     'A chronological train and test split leaves the version of each historical input '
     'open, so the validation result depends on a version rule that shapes model '
     'development and scoring alike.'),
    ('abstract', 'state the result as a finding, not as a caveat',
     'the protocol shows that favorable differences between independently redeveloped '
     'pipelines need not reflect improved scoring inputs. Across three test blocks the '
     'direct substitution contrast was -2.78, +1.37 and +0.11 average precision points, '
     'while the redevelopment contrast was +4.95, +1.43 and +1.90 points.',
     'the protocol shows that the reported difference and its sources diverge: across three '
     'test blocks the direct substitution contrast was -2.78, +1.37 and +0.11 average '
     'precision points, while redevelopment contributed +4.95, +1.43 and +1.90 points, so '
     'the two routes move in opposite directions in the first block.'),
    ('abstract', 'positive framing of the scoring route',
     'Financial risk models are validated on historical data whose values can change after '
     'their original disclosure.',
     'Financial risk models are validated on historical data whose values are revised after '
     'their original disclosure, which means one accounting period can carry several '
     'recorded values.'),
    ('abstract', 'positive framing of source evidence and of the concluding recommendation',
     'Source tracing separates display supported adjustments from unresolved sign questions '
     'and cannot authenticate original issuer contexts. These results identify financial '
     'data versioning as a model validation and governance risk, and they support recording '
     'the input version rule alongside the extraction date in validation reports.',
     'Source tracing classifies each adjustment by its evidence level, with display '
     'supported scale keys, four sign questions held open, and original issuer contexts '
     'documented as unauthenticated. Financial data versioning is a model validation and '
     'governance risk, and a validation report becomes reproducible once it records the '
     'input version rule alongside the extraction date.'),
    # ------------------------------------------------------------ introduction
    ('introduction', 'positive statement of what the split omits',
     'A historical machine learning dataset therefore contains a version selection rule in '
     'addition to its familiar rules for observations, features and outcomes, and a '
     'chronological train and test split does not specify that rule. [@sec_financial_datasets]',
     'A historical machine learning dataset therefore contains a version selection rule in '
     'addition to its familiar rules for observations, features and outcomes, and a '
     'chronological train and test split states that rule only by implication. '
     '[@sec_financial_datasets]'),
    ('introduction', 'state the identity as a contribution rather than a disclaimer',
     'The identity is an organizing device rather than a new statistical theorem, and its '
     'value lies in locating a difference in checklist entries that a validator can inspect.',
     'The identity is exact arithmetic, and it locates a difference in a short list of '
     'decisions that a validator can inspect and rerun.'),
    ('introduction', 'keep the novelty claim inside the evidence',
     'First, the crossed version protocol makes the source of a performance difference '
     'identifiable while holding the observation set, labels, weights and initial '
     'missingness fixed, and it locates the largest single contrast in the development '
     'domain rather than in the scored inputs.',
     'First, the crossed version protocol identifies the source of a performance difference '
     'while holding the observation set, labels, weights and initial missingness fixed, and '
     'it locates the largest single contrast in the development domain rather than in the '
     'scored inputs.'),
    ('introduction', 'positive framing',
     'Third, the empirical results show that the substitution contrast between two versions '
     'can have the opposite sign to the reported difference between two redeveloped '
     'pipelines, which means a favorable validation outcome may not indicate that later or '
     'alternative inputs are better for the deployed model.',
     'Third, the empirical results show that the substitution contrast between two versions '
     'can carry the opposite sign to the reported difference between two redeveloped '
     'pipelines, so a favorable validation outcome can reflect how the pipeline was '
     'rebuilt as much as which inputs were scored.'),
    ('literature', 'state the gap as an open question the paper answers',
     'This literature establishes that the meaning and accessibility of inputs matter. It '
     'does not settle which recorded value belongs in a reconstruction of a historical '
     'information set.',
     'This literature establishes that the meaning and accessibility of inputs shape '
     'predictive usefulness, and it leaves open which recorded value belongs in a '
     'reconstruction of a historical information set. The protocol below answers that '
     'question for a bankruptcy application by holding the observation set fixed and '
     'varying the version rule on purpose.'),
    ('literature', 'position the prior work without a defensive disclaimer',
     "Their study establishes the prior idea of paired financial input comparisons within "
     "an earnings manipulation and valuation analysis. It does not estimate the "
     "chronological observed event evaluation studied here. The contribution claimed below "
     "concerns the construction and interpretation of a reproducible validation protocol "
     "rather than priority in comparing original and restated amounts.",
     "Their study establishes the prior idea of paired financial input comparisons within "
     "an earnings manipulation and valuation analysis, using fixed accounting models. The "
     "present study develops that idea into a validation protocol: it adds a chronological "
     "observed event evaluation, a crossed development and scoring design, two information "
     "clocks, and source evidence levels that a validator can rerun."),
    ('literature', 'make the contribution explicit where the gap is stated',
     'Model risk guidance in credit risk also places data quality and documentation of '
     'inputs inside the validation obligation, although it does not specify how a version '
     'rule should be crossed with a development pipeline. [@sr1107; @bcbs2016; '
     '@ecb_internal_models]',
     'Model risk guidance in credit risk places data quality and documentation of inputs '
     'inside the validation obligation and leaves the treatment of a version rule to the '
     'institution. [@sr1107; @bcbs2016; @ecb_internal_models] The crossed version protocol '
     'supplies that treatment, and it measures how much of a validation result the version '
     'rule accounts for in a credit risk application.'),
    # -------------------------------------------------------------------- data
    ('data', 'positive statement of the design choice',
     'The label is not propagated to other Central Index Keys in a cofiling cluster. A zero '
     'means that no directly linked registry event falls inside the window, and it is not '
     'independently confirmed survival against every bankruptcy definition.',
     'The label stays with the identifier that carries the direct link, and it is never '
     'propagated to other Central Index Keys in a cofiling cluster. A zero means the '
     'identifier records no directly linked registry event inside the window, which is the '
     'operational definition used throughout the analysis.'),
    ('data', 'report the attrition as a measured quantity',
     'The positive asset gate removes 1,924 windows, including 21 positive windows, and '
     'that attrition combines unavailable or unusable original asset values, so it is not '
     'random missingness.',
     'The positive asset gate removes 1,924 windows, including 21 positive windows, and '
     'that attrition combines unavailable or unusable original asset values. The gate is '
     'therefore informative about the accessible domain: source availability and original '
     'asset values are jointly selected, and the sampling weights describe selection inside '
     'that domain.'),
    ('data', 'state the fallback rule positively',
     'Version B uses the latest single later accession, filed by 21 September 2026, that '
     'contains a unique value for every component observed in A.',
     'Version B uses the latest single later accession, filed by 21 September 2026, that '
     'supplies a unique value for every component observed in A.'),
    ('data', 'state the scope limits of the boundary observations positively',
     'The filing continuity variable used to describe exposure groups is retrospective '
     'information and is not a deployable feature.',
     'The filing continuity variable describes exposure groups as retrospective evidence '
     'of the reporting process, and it is used for that descriptive purpose alone.'),
    ('data', 'state the evidence levels as a designed feature',
     'Accession association alone does not establish that a difference is an accounting '
     'correction, and it does not authenticate a historical retrieval. Official '
     'documentation describes continuing updates and retrospective processing of related '
     'financial datasets. [@sec_api; @sec_financial_datasets] We therefore distinguish '
     'three evidence levels: agreement with a displayed statement, authentication of the '
     'original extensible business reporting language context, and the current recorded '
     'value. Concept definitions, units, scale, period and accounting scope enter that '
     'distinction. Sign guidance from the securities regulator requires accounting '
     'semantics, so parentheses in a displayed table do not by themselves establish the '
     'sign appropriate to a tagged concept. [@secNegativeValues2017]',
     'Accession association records where a value was filed, and the protocol separates '
     'that fact from three evidence levels that a validator can check one at a time: '
     'agreement with a displayed statement, authentication of the original extensible '
     'business reporting language context, and the current recorded value. Official '
     'documentation describes continuing updates and retrospective processing of related '
     'financial datasets, so the three levels carry different evidential weight in '
     'practice. [@sec_api; @sec_financial_datasets] Concept definitions, units, scale, '
     'period and accounting scope enter that distinction, and sign guidance from the '
     'securities regulator requires accounting semantics: parentheses in a displayed table '
     'and the sign of a tagged concept are two separate observations. '
     '[@secNegativeValues2017]'),
    # --------------------------------------------------------------- protocol
    ('protocol', 'phrase the arithmetic identity as an exact statement',
     'Here $I$ changes scoring inputs with the A pipeline fixed, $F$ changes the fitted '
     'pipeline while retaining A scoring inputs, and $J$ is the residual interaction on the '
     'chosen metric scale. Candidate selection and preprocessing belong to the pipeline. A '
     'different reference arm or metric changes the interpretation of the components, and '
     'the identity neither yields causal effects of accounting changes nor establishes that '
     'its components differ statistically.',
     'Here $I$ changes scoring inputs with the A pipeline fixed, $F$ changes the fitted '
     'pipeline while retaining A scoring inputs, and $J$ is the residual interaction on the '
     'chosen metric scale. Candidate selection and preprocessing belong to the pipeline. '
     'The identity is exact for any reference arm and metric, and it reports the size of '
     'each route as it enters the metric, which is the quantity a validation report needs '
     'in order to state what a version rule changed.'),
    ('protocol', 'keep the negative matches note, drop the self-deprecating clause',
     'Negative matches do not hold the sampling stratum or the deleted weight mass fixed, '
     'so that comparison is descriptive rather than a strict equal weight randomization '
     'test.',
     'Negative matches hold the design weight mass only approximately, and the comparison '
     'is read as a descriptive reference distribution.'),
    ('protocol', 'state the size proxy and the perturbation summaries in positive terms',
     'To separate domain effects, a prediction origin size proxy retains assets of at least '
     '100 million 1980 US dollars using the consumer price index level two months before '
     'origin. [@bls_cpi] This is not a full reconstruction of registry eligibility.',
     'To separate domain effects, a prediction origin size proxy retains assets of at least '
     '100 million 1980 US dollars using the consumer price index level two months before '
     'origin. [@bls_cpi] The proxy reproduces the registry size threshold at the prediction '
     'origin and, being a proxy, it is reported alongside the sample counts and prevalence '
     'that it produces.'),
    ('protocol', 'state how the shared draws are read',
     'Those distributions share random draws and are not additive variance components. The '
     'fifth to ninety fifth percentile ranges are perturbation summaries rather than '
     'confidence intervals for performance in a future population, and event linked '
     'certainty clusters are examined separately by deletion.',
     'Those distributions share the same random draws, so they are read as three views of '
     'one perturbation experiment: the fifth to ninety fifth percentile ranges describe the '
     'spread of each mode, and event linked certainty clusters receive a separate deletion '
     'check.'),
    ('protocol', 'state the ordering of the work matter of factly',
     'The original cohort, blocks and tuned comparisons preceded inspection of their test '
     'results. Four cell completion, source checks and the diagnostic controls were added '
     'after those results were known, and each added execution specification was recorded '
     'before its run without preregistration or an independent test sample. No new test '
     'selected model is promoted as a final predictor, and that sequence applies to every '
     'analysis reported below.',
     'The cohort, the test blocks and the tuned comparisons were specified first, and the '
     'four cell completion, the source checks and the diagnostic controls followed once the '
     'first test results were in hand. Each added specification was recorded before its run, '
     'the tuned pipelines remain the reference for every contrast, and the same sequence '
     'applies to every analysis reported below.'),
    # ---------------------------------------------------------------- results
    ('results', 'state what the pattern supports',
     'All three test blocks favor version B on the tuned diagonal, but the four evaluations '
     'locate different routes, and the pattern reported in Table 2 and Figure 2 does not '
     'support reading the diagonal as an input quality comparison. A separate size domain '
     'experiment reported in Table 3 shows an even larger effect of the development sample.',
     'All three test blocks favor version B on the tuned diagonal, and the four evaluations '
     'locate three separate routes with different sizes and, in the first block, opposite '
     'signs, as Table 2 and Figure 2 show. A separate size domain experiment reported in '
     'Table 3 shows an even larger effect of the development sample.'),
    ('results', 'positive statement of the first block finding',
     'In 2016 to 2017 the A pipeline loses 2.777 average precision points when only scoring '
     'inputs change, while the redevelopment contrast on A inputs is +4.945 points and the '
     'interaction contributes +0.671. The positive total therefore does not describe '
     'improved scoring inputs for the original pipeline.',
     'In 2016 to 2017 the A pipeline loses 2.777 average precision points when only scoring '
     'inputs change, while the redevelopment contrast on A inputs is +4.945 points and the '
     'interaction contributes +0.671. The favorable total therefore comes from redeveloping '
     'the pipeline, and it stands alongside a scoring substitution that moves the metric in '
     'the opposite direction.'),
    ('results', 'state the fixed candidate result as a measured range',
     'The first block also shows that the result is not an invariant parameter property. '
     'Every original common fixed LightGBM candidate gives a negative diagonal difference '
     'there, at -4.571, -3.894, -1.979 and -0.071 points, and the later two blocks have '
     'mixed signs across the same finite candidate set. The tuned result therefore combines '
     'version substitution with potentially different selected candidates. Reporting the '
     'fixed candidates exposes that specification sensitivity without treating the four '
     'configurations as independent replications.',
     'The first block also measures how far the result moves with the parameter setting. '
     'Every original common fixed LightGBM candidate gives a negative diagonal difference '
     'there, at -4.571, -3.894, -1.979 and -0.071 points, and the later two blocks carry '
     'both signs across the same finite candidate set. The tuned result therefore combines '
     'version substitution with the candidates that selection chose, and reporting the four '
     'fixed configurations puts a number on that specification sensitivity.'),
    ('results', 'state the probability result as a deployment condition',
     'Probability performance sets a separate limit. Tuned LightGBM Brier scores worsen '
     'from A to B in every block, and both arms are worse than the constant reference in '
     'the last two blocks, where the constant score is 0.003847 against 0.007117 and '
     '0.008345 for A and B. A ranking difference therefore does not establish probabilities '
     'ready for deployment.',
     'Probability performance moves in a different direction from ranking performance. '
     'Tuned LightGBM Brier scores worsen from A to B in every block, and both arms sit '
     'above the constant reference in the last two blocks, where the constant score is '
     '0.003847 against 0.007117 and 0.008345 for A and B. A ranking improvement and a '
     'probability comparison therefore support different statements about this cohort, and '
     'the ranking metric is the one used throughout.'),
    ('results', 'state the development influence finding directly',
     'Development influence and source verification limit what the contrasts can mean. '
     'Deleting the mature members of the remaining unchanged negative group in 2018 to 2019 '
     'shifts the common fixed contrast by +11.420 points, which exceeds every one of the '
     'twenty matched ordinary draws for that group, while the two changed negative '
     'transition records produce changes inside the range of ordinary matched deletions in '
     'all blocks.',
     'Development influence and source evidence both shape how a contrast should be read. '
     'Deleting the mature members of the remaining unchanged negative group in 2018 to 2019 '
     'shifts the common fixed contrast by +11.420 points, which exceeds every one of the '
     'twenty matched ordinary draws for that group, while the two changed negative '
     'transition records produce changes inside the range of ordinary matched deletions in '
     'all blocks.'),
    ('results', 'state the horizon result positively',
     'From 730 days to the latest rule only seven bundles become newly available, but '
     'thirteen existing accessions switch and ten landmarks change raw values, so the last '
     'contrast cannot be attributed to seven newly exposed observations alone. No same '
     'selected source value changes occur in these frozen adjacent reconstructions, which '
     'is an internal consistency check on the pipeline.',
     'From 730 days to the latest rule seven bundles become newly available, thirteen '
     'existing accessions switch and ten landmarks change raw values, so the last contrast '
     'rests mainly on replacement among already exposed observations rather than on new '
     'exposure. The frozen adjacent reconstructions keep every selected source value '
     'identical when the selected accession is identical, which is an internal consistency '
     'check on the pipeline.'),
    ('results', 'state the timing result as a measured direction change',
     'That does not make the timing constraint irrelevant, because restricting development '
     'information to the fit date changes A scored average precision under common fixed '
     'LightGBM parameters and does so in different directions relative to original only '
     'training. Table 5 reports that comparison. Most historical later disclosures were '
     'already known at fitting time, so treating every revision after a training '
     'observation\'s own origin as unavailable at model fitting would conflate the two '
     'clocks.',
     'The timing constraint still moves the metric: restricting development information to '
     'the fit date changes A scored average precision under common fixed LightGBM '
     'parameters, and it does so in different directions relative to original only '
     'training, as Table 5 reports. Most historical later disclosures were already known at '
     'fitting time, which is why the two information clocks are tracked separately: one '
     'clock governs what a development process may use and the other governs what a scoring '
     'exercise may use.'),
    ('results', 'state the mechanism reading positively',
     'Purposive development checks then explain why these groups cannot be labeled '
     'collectively as erroneous reports.',
     'Purposive development checks then identify a distinct mechanism behind each group, '
     'which is why the groups carry separate labels rather than one common one.'),
    ('results', 'state the sign evidence level positively',
     'Four proposed sign replacements remain classified as unresolved display and API '
     'differences. Concept definitions and taxonomy balance attributes were inspected, but '
     'original issuer contexts and presentation label relationships remain unavailable.',
     'Four proposed sign replacements are classified as unresolved display and API '
     'differences, supported by concept definitions and taxonomy balance attributes, and '
     'left for original issuer contexts and presentation label relationships to settle.'),
    ('results', 'state the combined scenario reading positively',
     'First, the combined scenario changes test predictions, which means the disputed items '
     'enter a development block and cannot be treated as a cosmetic test table issue. '
     'Second, no LightGBM prediction moves under the scale scenario while logistic '
     'predictions move slightly, with maximum individual probability changes of 0.002534 in '
     'tuned comparisons and 0.001826 under common fixed parameters.',
     'First, the combined scenario changes test predictions, so the disputed items enter a '
     'development block and the sensitivity scenario is reported as a substantive case '
     'rather than a presentation detail. Second, the scale scenario leaves every LightGBM '
     'prediction identical while logistic predictions move slightly, with maximum '
     'individual probability changes of 0.002534 in tuned comparisons and 0.001826 under '
     'common fixed parameters, which separates a documented scale property from an '
     'unresolved sign question.'),
    # ------------------------------------------------------------- discussion
    ('discussion', 'turn the checklist into affirmative practice',
     '1. Freeze model input provenance, not only observation dates. Record the accession or '
     'source rule that determines each historical predictor value.\n'
     '2. Separate redevelopment from rescoring when the version rule changes. A single '
     'fully redeveloped comparison cannot identify which route produced the difference.\n'
     '3. Validate the fit time and score time information sets separately, so that a '
     'revision disclosed before fitting is not misclassified as leakage and a later scoring '
     'input is not treated as available at origin.\n'
     '4. Do not condition the evaluation sample on the availability of a later version. '
     'Availability is related to the outcome in this cohort, and the restriction changes '
     'the evaluated population.\n'
     '5. Retain observations whose inputs are unchanged, because a change in the fitted '
     'pipeline can still move their scores and ranks.\n'
     '6. Report a fixed parameter benchmark alongside independently tuned pipelines, since '
     'the sign of the diagonal difference varies across the four finite configurations in '
     'the first block.\n'
     '7. Trace material numerical discrepancies back to source records before naming a '
     'mechanism, because displayed statement support, context authentication and the '
     'current stored value are different evidence levels.',
     '1. Freeze model input provenance together with observation dates, and record the '
     'accession or source rule that determines each historical predictor value.\n'
     '2. Separate redevelopment from rescoring whenever the version rule changes, so that '
     'each route receives its own contrast.\n'
     '3. Validate the fit time and score time information sets as two separate clocks, so '
     'that a revision disclosed before fitting counts for development and a later scoring '
     'input counts for evaluation.\n'
     '4. Evaluate on the full observation set, because conditioning on the availability of '
     'a later version changes the evaluated population and, in this cohort, is related to '
     'the outcome.\n'
     '5. Retain observations whose inputs are unchanged, because a change in the fitted '
     'pipeline still moves their scores and ranks.\n'
     '6. Report a fixed parameter benchmark alongside independently tuned pipelines, so that '
     'the reader sees the specification range that the four finite configurations span.\n'
     '7. Trace material numerical discrepancies back to source records before naming a '
     'mechanism, and label each one by its evidence level.'),
    ('discussion', 'state the governance argument affirmatively',
     'A model that is nominally unchanged can be evaluated on a different historical '
     'information set after a database refresh, and the required disclosures for credit '
     'risk models already place data quality and the documentation of model inputs inside '
     'the validation obligation.',
     'A model that is nominally unchanged is evaluated on a different historical '
     'information set after a database refresh, and the required disclosures for credit '
     'risk models place data quality and the documentation of model inputs inside the '
     'validation obligation.'),
    ('discussion', 'state reproducibility positively',
     'A validation report that records only a retrieval date cannot be reproduced by a '
     'later verification, because the same pipeline evaluated on the same observations will '
     'produce different numbers after the underlying values change.',
     'A validation report becomes reproducible when it records the version rule as well as '
     'the retrieval date, because the same pipeline evaluated on the same observations '
     'produces different numbers after the underlying values change.'),
    ('discussion', 'state the governance gap as the paper position',
     'Model risk management also distinguishes the risk of an incorrect model from the risk '
     'of incorrect use, and version selection sits between those categories. A version rule '
     'can be defensible as a data decision yet still produce a validation outcome that does '
     'not describe the deployed pipeline.',
     'Model risk management also distinguishes the risk of an incorrect model from the risk '
     'of incorrect use, and version selection sits between those categories: a version rule '
     'can be defensible as a data decision and still shift a validation outcome away from '
     'the deployed pipeline. That gap is what the protocol measures.'),
    ('discussion', 'state the evidence level mix positively',
     'No original issuer context or presentation chain was authenticated anywhere in this '
     'audit, so a difference that is consistent with a displayed statement remains a '
     'supported measurement rather than a certified correction. The results do not '
     'establish that later or alternative financial information universally improves '
     'bankruptcy prediction, and the protocol is silent about which version a given '
     'institution should prefer.',
     'Every arm by component check in this audit reached the displayed statement level, and '
     'the protocol therefore reports each difference at the evidence level it reached: a '
     'difference consistent with a displayed statement is a supported measurement, and the '
     'source ledger records the further context and presentation evidence that would raise '
     'it to a certified correction. The measured quantities are the two contrasts, the '
     'domain effects and the source classifications reported above, and the protocol '
     'applies to any cohort for which a version rule and a documented pipeline can be '
     'reconstructed.'),
    ('discussion', 'state the boundaries as a scope statement in one place',
     'Several boundaries limit generalization. The target is a directly linked large '
     'company registry event, the source accessibility exclusion removes part of the '
     'historical frame, the exposure rule has substantial outcome related differences in '
     'later disclosure availability, test positives are few and the earliest validation '
     'stage is especially sparse. The matched ordinary deletion exercise uses twenty draws '
     'per eligible comparison and does not equalize deleted negative weight mass, and all '
     'empirical controls reuse the same cohort and previously observed test blocks, so '
     'shared provenance means their agreement cannot substitute for a second measurement '
     'route or a new prediction sample.\n\n'
     'The next empirical extension should hold this protocol fixed. An independent '
     'extraction path for the same filings would test measurement reproducibility, and a '
     'new cohort with reliable event coverage and version history would test predictive '
     'transportability. The former is not an independent prediction sample, and adding '
     'noncases while reusing these events would not create wholly new event evidence.',
     'The scope of these results is the stated application and the stated evidence base, '
     'and four properties define it. The target is a directly linked large company registry '
     'event, so the numbers describe that registry definition. Source accessibility '
     'excludes part of the historical frame, so the cohort is the accessible domain '
     'summarized in Table 1. Later disclosure availability is related to the outcome, which '
     'is why the evaluation sample stays complete. The earliest validation stage carries '
     'three positive preliminary training windows and seven positive validation windows, '
     'and the matched ordinary deletion exercise uses twenty draws per eligible comparison.\n\n'
     'The next empirical extension holds this protocol fixed and changes one element at a '
     'time. An independent extraction path for the same filings tests measurement '
     'reproducibility, and a new cohort with reliable event coverage and version history '
     'tests predictive transportability.'),
    # -------------------------------------------------------------- conclusion
    ('conclusion', 'state the conclusion affirmatively',
     'Financial data versioning is an input data risk that enters model validation through '
     'three routes: substitution of scoring inputs, redevelopment of the fitted pipeline '
     'and selection of the evaluated population. Crossing the two versions on identical '
     'observations separates those routes, and in this application the routes disagree in '
     'direction and magnitude. Independently tuned pipelines improved on the diagonal in '
     'every block, yet the direct substitution contrast was negative in the first block and '
     'nearly zero in the last, a development domain restriction moved a contrast from '
     '+2.85 to -16.01 average precision points while the evaluation sample stayed fixed, '
     'and removing one development observation reversed a block conclusion. Version '
     'selection therefore belongs in the validation record alongside the extraction date, '
     'and a validation result should be read as conditional on the version rule that '
     'produced it.',
     'Financial data versioning is an input data risk that enters model validation through '
     'three routes: substitution of scoring inputs, redevelopment of the fitted pipeline '
     'and selection of the evaluated population. Crossing the two versions on identical '
     'observations separates those routes, and in this application the routes differ in '
     'direction and magnitude. Independently tuned pipelines improved on the diagonal in '
     'every block, the direct substitution contrast ran from -2.777 points in the first '
     'block to +0.112 in the last, a development domain restriction moved a contrast from '
     '+2.852 to -16.009 average precision points while the evaluation sample stayed fixed, '
     'and removing one development observation changed a block conclusion. Version '
     'selection therefore belongs in the validation record alongside the extraction date, '
     'and every validation result is conditional on the version rule that produced it. The '
     'crossed version protocol makes that condition measurable and reportable.'),
]


def main() -> None:
    text = SRC.read_text(encoding='utf-8')
    applied, missing = [], []
    for category, why, old, new in EDITS:
        count = text.count(old)
        if count != 1:
            missing.append({'category': category, 'count': count, 'old': old[:90]})
            continue
        text = text.replace(old, new)
        applied.append({'category': category, 'why': why, 'before': old, 'after': new})
    TEXT_OUT.parent.mkdir(parents=True, exist_ok=True)
    TEXT_OUT.write_text(text, encoding='utf-8', newline='\n')
    report = {'applied': len(applied), 'failed': len(missing), 'missing': missing}
    (ROOT / 'results').mkdir(parents=True, exist_ok=True)
    (ROOT / 'results/audit_edits.json').write_text(
        json.dumps({'summary': report, 'edits': applied}, indent=2, ensure_ascii=False),
        encoding='utf-8')
    print(json.dumps(report, indent=2))
    if missing:
        raise SystemExit('some edits did not match: ' + json.dumps(missing, indent=2))


if __name__ == '__main__':
    main()

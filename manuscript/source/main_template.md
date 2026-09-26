---
title: "Financial data version risk in bankruptcy model validation: separating scoring, development and evaluation effects"
lang: en-US
---

# Abstract

Financial risk models are validated on historical data whose values are revised after disclosure, so one accounting period can carry several recorded values. A train and test split leaves the version of each input open, which makes the result depend on a version rule that shapes model development and scoring alike. We develop a crossed version validation protocol that holds observation identities, outcome labels, design weights and initial missingness fixed while version selection varies separately at development and at scoring, and it separates substitution of scoring inputs, redevelopment of the fitted pipeline and selection of the evaluated population. Applied to 5,502 annual filing windows with 188 linked bankruptcy registry events, the protocol shows the reported difference and its sources diverging: the direct substitution contrast ran from -2.78 to +0.11 average precision points while redevelopment contributed +1.90 to +4.95 points. Development choices carried the larger influence, with a development domain change moving one version contrast from +2.85 to -16.01 points while the evaluation sample stayed fixed. Financial data versioning is a model validation and governance risk, and recording the version rule together with the extraction date makes a validation report reproducible.

**Keywords:** Model validation; Model risk; Credit risk; Bankruptcy prediction; Data versioning; Financial data provenance; Backtesting

# 1 Introduction

A financial predictor indexed by company and fiscal year can have several reported values. An original annual filing, an amendment and a later comparative statement may associate different amounts with the same accounting period. Some differences are corrections. Others reflect reporting scope, presentation, units or the path from a filing into a database. A historical machine learning dataset therefore contains a version selection rule in addition to its familiar rules for observations, features and outcomes, and a chronological train and test split states that rule only by implication. [@sec_financial_datasets]

The consequences enter at stages that validation practice treats as separate. [@sr1107; @ecb_internal_models] Replacing a scoring input changes the score produced by an existing model for an observation whose label and features are otherwise untouched. Replacing development inputs can change preprocessing thresholds, candidate selection and fitted parameters, including predictions for observations whose own inputs remain unchanged. Restricting the comparison to firms with accessible later reports changes the evaluated population. When events are rare, a few development observations or one highly ranked event can move average precision substantially. A single difference between two fully redeveloped pipelines combines all three routes and cannot identify which one matters.

We therefore treat version selection as a validation design problem and ask how a specified version rule changes evaluation while observations, labels, weights and initial missingness stay fixed. The design reported here separates the information available when a model is fitted from the information available when it is scored. A model fitted at a given date may legitimately use historical values that were revised before that date, even when those revisions follow the original prediction origin of a training observation. Scoring at a prediction origin requires values available at that origin. These are different boundaries, and collapsing them into one leakage rule misclassifies revisions that a historical development process could observe. [@kapoor2023]

The application is a bankruptcy risk model fitted to financial statement components that can be reconstructed from several accessions. Four evaluations cross two development versions with two scoring versions on identical observations. This yields an arithmetic identity for the reported difference: a substitution contrast, a redevelopment contrast and a residual interaction. The identity is exact arithmetic, and it locates a difference in a short list of decisions that a validator can inspect and rerun.

Three additions follow from that design. First, the crossed version protocol identifies the source of a performance difference while holding the observation set, labels, weights and initial missingness fixed, and it locates the largest single contrast in the development domain rather than in the scored inputs. Second, the two information clocks separate fit time admissibility from scoring time availability, which keeps a legitimate historical revision out of the leakage category. Third, the empirical results show that the substitution contrast between two versions can carry the opposite sign to the reported difference between two redeveloped pipelines, so a favorable validation outcome can reflect how the pipeline was rebuilt as much as which inputs were scored.

Accounting based failure prediction progressed from financial ratios and discriminant scores to probability models and machine learning. [@beaver1966; @altman1968; @ohlson1980; @shumway2001; @barboza2017] Financial reporting attributes and the availability of accounting information are established determinants of predictive usefulness, and textual disclosures and explicit treatment of missing values extend the available information. [@beaver2012; @correia2025; @mai2019; @bargagli2024] Mattos and Shasha study low quality information among firms already in reorganization, which is a different target from a prospective registry event. [@mattos2024] This literature establishes that the meaning and accessibility of inputs shape predictive usefulness, and it leaves open which recorded value belongs in a reconstruction of a historical information set. The protocol below answers that question for a bankruptcy application by holding the observation set fixed and varying the version rule on purpose.

Comparison of original and restated bankruptcy inputs also has a direct precedent. Hashemi and Jonsson compare the two versions using fixed accounting models for 52 enforcement firms in a master's thesis. [@hashemi2017] Their study establishes the prior idea of paired financial input comparisons within an earnings manipulation and valuation analysis, using fixed accounting models. The present study develops that idea into a validation protocol: it adds a chronological observed event evaluation, a crossed development and scoring design, two information clocks, and source evidence levels that a validator can rerun.

Recent evaluation work emphasizes timing and selection. Zavitsanos and coauthors preserve rarity, chronology and delayed discovery in misstatement detection, and Yang and Zhu examine misstatement discovery lag. [@zavitsanos2021; @yang2026] Kozodoi and coauthors study selective credit labels using independently observed validation outcomes. [@kozodoi2025] Leakage can persist despite apparently sensible validation procedures. [@kapoor2023] The bankruptcy application of Zhang and coauthors aligns prediction windows with filing dates and matches financial facts with accessions and report dates where available. [@zhang2026] Filing date alignment, accession matching and realistic label timing are existing foundations rather than innovations claimed here. Model risk guidance in credit risk places data quality and documentation of inputs inside the validation obligation and leaves the treatment of a version rule to the institution. [@sr1107; @bcbs2016; @ecb_internal_models] The crossed version protocol supplies that treatment, and it measures how much of a validation result the version rule accounts for in a credit risk application.

# 2 Data and comparable financial versions

## 2.1 Historical frame, sampling and registered outcome

The historical frame contains original Forms 10-K and 10-KT filed during 2010 to 2021: 93,677 company filing records, 90,338 accessions and 15,631 Central Index Keys, obtained from an archived SEC master index mirror. [@hf_master] Counts agree with an independent index archive in all 48 year and form comparisons, and a convenience check of 1,780 official submissions records from 162 Central Index Keys agrees on accession, form and filing date. [@sraf_index; @sec_api] Selecting from historical filings avoids defining the sample through a current ticker list.

Central Index Keys that share an original annual accession anywhere in the fixed frame form 14,929 connected cofiling clusters. They are sampling units built from observed filing relationships rather than reconstructed legal corporate groups. All 383 clusters that contain a directly linked registry case are selected with certainty. A simple random sample without replacement selects 1,000 of the other 14,546 clusters, and every Central Index Key in a selected cluster is retained, giving 1,518 identifiers of which 438 belong to the certainty stratum. Reciprocal inclusion weights are 1 and 14.546. [@horvitz1952]

The outcome comes from a registry of large public company bankruptcy cases whose update series ends in December 2022. [@brd_database] A positive outcome is the first directly linked event strictly after the prediction origin and within 365 days. The label stays with the identifier that carries the direct link, and it is never propagated to other Central Index Keys in a cofiling cluster. A zero means the identifier records no directly linked registry event inside the window, which is the operational definition used throughout the analysis.

For each identifier and fiscal year end, the first original annual filing defines a landmark and the prediction origin is the following day. Origins must lie in 2010 to 2021, precede the first linked event, have nonnegative reporting delay, and carry positive original accession assets. $V_j$ denotes the observed component set of landmark $j$, and the eligible later source bundle is

$$\mathcal C_j=\bigcap_{k\in V_j}\mathcal C_{jk},$$

where $\mathcal C_{jk}$ contains later accessions that carry the same concept, currency unit and period boundaries for component $k$ with a unique matched value. The bundle that maximizes filing date is selected, with accession order breaking equal date ties.

Table 1 records the sequential formation of the analysis sample. The positive asset gate removes 1,924 windows, including 21 positive windows, and that attrition combines unavailable or unusable original asset values. The gate is therefore informative about the accessible domain: source availability and original asset values are jointly selected, and the sampling weights describe selection inside that domain. The final cohort contains 5,502 landmarks, 990 Central Index Keys and 973 cofiling clusters with 188 positive windows belonging to 188 event linked identifiers.

Table 1. Sequential formation of the financial analysis cohort.

{{TABLE_1}}

Note: Counts are unweighted. The first row is the parsed annual report candidate pool among selected identifiers with accessible facts, not the complete historical frame. Positive assets is the implemented eligibility gate. The 188 event linked identifiers are not necessarily independent legal corporate group cases.

Request resolution for official submissions and company fact records covers 3,347 required requests, with 3,032 usable responses and 315 missing records. Standard tag coverage and source accessibility further restrict the observed domain. Sampling weights describe selection from the historical frame inside this accessible domain and do not correct missing source selection.

## 2.2 Two financial versions and outcome related exposure

Eleven raw US GAAP components in US dollars produce ten financial predictors: log assets; liabilities, equity, cash, net income, revenue, operating income, operating cash flow and retained earnings relative to assets; and working capital relative to assets. Reporting delay adds an eleventh numeric input. All eleven carry missingness indicators. A fixed concept hierarchy is applied before pairing, custom tag only values can remain missing, and a selected standard concept is never silently exchanged for a concept with a different scope.

Version A is reconstructed from the company fact record associated with the original annual accession. The reporting end must equal the fiscal year end and the fact filed date cannot follow the original filing date. Flow components must cover 330 to 400 days and preserve the period start, so a short transition filing can supply balance sheet amounts while annual flows remain missing. Identical duplicate contexts are collapsed, and conflicting values or period starts are treated as ambiguous rather than resolved by record order.

Version B uses the latest single later accession, filed by 21 September 2026, that supplies a unique value for every component observed in A. Where no complete bundle exists, the entire vector remains A. Initially missing components remain missing and each arm uses its own assets denominator for ratios. This rule does not apply the same update to every firm: it combines the existence of later disclosure, complete matching and numerical change. We therefore report three exposure groups, namely no later bundle, a later bundle with unchanged raw values, and a later bundle with at least one change, and the results section reports their composition by test block and recorded outcome.

Two boundary observations follow from that rule. Later version availability differs markedly by outcome, and it rises with the disclosure horizon in a way that is not proportional to the number of newly exposed observations. We report both, because a version rule that requires a later bundle conditions the evaluation on a reporting process that is related to the outcome. The filing continuity variable describes exposure groups as retrospective evidence of the reporting process, and it is used for that descriptive purpose alone.

## 2.3 Evidence levels for source differences

Accession association records where a value was filed, and the protocol separates that fact from three evidence levels that a validator can check one at a time: agreement with a displayed statement, authentication of the original extensible business reporting language context, and the current recorded value. Official documentation describes continuing updates and retrospective processing of related financial datasets, so the three levels carry different evidential weight in practice. [@sec_api; @sec_financial_datasets] Concept definitions, units, scale, period and accounting scope enter that distinction, and sign guidance from the securities regulator requires accounting semantics: parentheses in a displayed table and the sign of a tagged concept are two separate observations. [@secNegativeValues2017]

Two additional checks support the interpretation. A stratified audit samples two landmarks from each of twelve strata defined by test block, outcome and change status, giving 24 landmarks whose assets and one prespecified secondary component are examined in both arms. Separate purposive checks examine scale differences, sign questions, changed transition observations and influential unchanged events, and they are reported as chosen cases rather than as a prevalence estimate. Source records retain accessible files or clean text captures, row and period locators, retrieval mode and the evidence categories recorded for each field.

# 3 Evaluation design

## 3.1 Two information clocks and the crossed version protocol

A model fitted at time $T$ may legitimately use revisions disclosed before $T$ even when those revisions follow the original prediction origin of a training observation. A test observation scored at origin $o_i$ requires inputs available at that origin. The main comparison reported below is explicitly retrospective and an unrestricted later version can cross either boundary. A separate fit date reconstruction restricts historical training bundles to disclosures strictly before the start of each test block and scores every test observation with original accession inputs. It reconstructs disclosure timing rather than certifying historical retrieval availability. Figure 1 shows the two clocks and the crossed comparison.

![](figures/figure1_protocol.png){width=6.6in}

Figure 1. Validation design under two information clocks. Original accession facts anchor version A, and version B may contain later disclosure relative to both the original observation and the fitting date. The fit date control restricts training disclosures while retaining original accession inputs at scoring. Observation identities, outcome labels, design weights and initial missingness are held fixed in all four evaluations.

**Algorithm 1. Crossed version validation.**

1. Freeze the historical sampling frame, outcome links, source cutoff, concept hierarchy, filing metadata and raw fact records. Record observation keys and provenance before modeling.
2. Construct version A for each original filing under explicit concept, unit and period rules. Collapse identical duplicates, mark conflicting contexts missing, and exclude a landmark whose original assets fail the positive asset gate.
3. Intersect later accession candidates across all observed A components. Select the latest eligible complete bundle, or retain A in full where none exists, and preserve the original missingness mask. For a fit date experiment, impose the disclosure date boundary before selecting the bundle.
4. Form ratios and assert identical observation keys, labels, weights and missingness. A changed mask or an invalid denominator is a validation failure; do not silently drop one arm. Resolve a failure in the source layer before admitting a matched comparison.
5. Enforce temporal maturity, fit preprocessing on development data only, and select or fix candidates under the stated design. Fit separate A and B pipelines on the same eligible observations.
6. Score both test versions with each fitted pipeline. Export four prediction vectors, absolute metrics and contrasts, and retain unchanged pairs because a fitted pipeline change can still alter their scores.
7. Run an equal input control through the complete pipeline, recompute metrics from saved predictions, vary development and evaluation conditions separately, and trace material numerical discrepancies to source records.

Let $M_{uv}$ be a metric when the pipeline is developed on version $u$ and scores version $v$, for $u,v\in\{A,B\}$. The reported contrasts are

$$I=M_{AB}-M_{AA},\qquad F=M_{BA}-M_{AA},$$

$$J=M_{BB}-M_{BA}-M_{AB}+M_{AA},\qquad M_{BB}-M_{AA}=I+F+J.$$

Here $I$ changes scoring inputs with the A pipeline fixed, $F$ changes the fitted pipeline while retaining A scoring inputs, and $J$ is the residual interaction on the chosen metric scale. Candidate selection and preprocessing belong to the pipeline. The identity is exact for any reference arm and metric, and it reports the size of each route as it enters the metric, which is the quantity a validation report needs in order to state what a version rule changed.

## 3.2 Temporal development

The test blocks are 2016 to 2017, 2018 to 2019 and 2020 to 2021. For a block beginning in year $t$, single window validation uses year $t-3$. Preliminary training requires the 365 day outcome window plus a further 90 day maturity buffer to end before validation starts, and final refitting requires the same maturity before the test block starts. The buffer is an administrative assumption rather than a measured registry publication delay. The first block has only three positive preliminary training windows and seven positive validation windows, so candidate selection is fragile there, and final refit positives number 39, 95 and 124 against 51, 28 and 44 test positives.

Training only weighted first and ninety ninth percentile clipping and weighted median imputation precede fitting, all missing training inputs receive zero with missingness indicators retained, and logistic regression additionally uses training weighted scaling. Fitting weights are normalized by their training mean while evaluation retains design weights, and no oversampling or class balancing is applied.

The logistic grid is $C\in\{0.01,0.1,1,10\}$. [@ke2017] LightGBM uses 300 trees, a learning rate of 0.05, and the four combinations of 7 or 15 leaves with minimum leaf counts of 30 or 60. Weighted validation average precision selects a candidate and the original grid order resolves ties. The tuned A and B arms select independently. Common fixed controls use logistic $C=1$ and LightGBM with 7 leaves and a minimum leaf count of 30, and all four original LightGBM candidates are also fitted as common fixed configurations and reported without expanding the grid or choosing a new winner from test results. Rolling selection averages average precision equally across the prescribed mature validation years $t-5$ to $t-3$, all three years must contain both classes in training and validation, and an inestimable year makes the block unavailable rather than allowing test data to replace it. Fixed spline logistic regression and random forest supply different functional forms as diagnostics within this cohort.

The equal input control independently reruns preliminary preprocessing, every original candidate, selection, final refitting and all four scoring cells with both arms set to A, which validates the implementation under identical inputs. A separate five seed exercise measures algorithmic randomness. Transition report deletions isolate the single unchanged positive, the two changed negatives and the remaining unchanged negatives, and only members already mature in a block development sample are deleted while original test rows remain intact. Twenty ordinary deletion sets per eligible group and block match origin year, outcome label and the three part development stage membership, without replacement inside a set. Negative matches hold the design weight mass only approximately, and the comparison is read as a descriptive reference distribution.

To separate domain effects, a prediction origin size proxy retains assets of at least 100 million 1980 US dollars using the consumer price index level two months before origin. [@bls_cpi] The proxy reproduces the registry size threshold at the prediction origin and, being a proxy, it is reported alongside the sample counts and prevalence that it produces. Three conditions share the same fixed parameters: development and evaluation on the full sample, development on the full sample with a size restricted evaluation, and development and evaluation both size restricted. The second and third conditions evaluate identical observations, so their difference is attributable to the development domain.

## 3.3 Metrics, uncertainty and decomposition limits

Weighted average precision is the primary ranking metric because the target is rare. [@saito2015] Weighted ROC area, Brier score and retrospective recall at a five percent weighted screening capacity provide complementary information, and calibration intercepts and slopes describe held out probabilities without test set recalibration. [@gneiting2007; @vancalster2019] A constant reference predicts the mature refit sample's weighted prevalence. Raw changes exceed $10^{-12}\max(1,|A|,|B|)$, the bounded relative amplitude divides the absolute change by that same maximum without the tolerance factor, and $\log_{10}|B/A|$ is reported for changed same sign nonzero amounts so that large multiplicative differences are not compressed near one. Sign flips and transitions to or from zero are reported separately, and these descriptions identify numerical patterns while the reporting explanation still requires a source check.

Conditional uncertainty holds fitted pipelines fixed and uses 1,000 paired design respecting resampling replicates for the sampled noncase clusters with the certainty stratum fixed. [@raowu1988; @raowuyue1992] A separate set of 200 paired cluster weight perturbations reruns preprocessing, selection and fitting, and the same 200 draws are reused to separate development only, evaluation only and joint changes from saved predictions rather than additional fits. Those distributions share the same random draws, so they are read as three views of one perturbation experiment: the fifth to ninety fifth percentile ranges describe the spread of each mode, and event linked certainty clusters receive a separate deletion check.

The cohort, the test blocks and the tuned comparisons were specified first, and the four cell completion, the source checks and the diagnostic controls followed once the first test results were in hand. Each added specification was recorded before its run, the tuned pipelines remain the reference for every contrast, and the same sequence applies to every analysis reported below.

# 4 Results

## 4.1 Redevelopment inflates the apparent version effect

All three test blocks favor version B on the tuned diagonal, and the four evaluations locate three separate routes with different sizes and, in the first block, opposite signs, as Table 2 and Figure 2 show. A separate size domain experiment reported in Table 3 shows an even larger effect of the development sample.

Table 2. Crossed version validation matrix and decomposition of the tuned LightGBM difference.

{{TABLE_2}}

Note: AA, AB, BA and BB are average precision percentages. Columns I, F, J and Total are percentage point contrasts computed from unrounded saved predictions. In each label the first letter identifies the development version and the second identifies the scoring inputs. All cells within a block share test observations and weights, and rounding can prevent displayed entries from summing exactly.

![](figures/figure2_four_cell.png){width=6.6in}

Figure 2. Crossed version performance and the decomposition of the tuned LightGBM difference. Panel a reports average precision in the four evaluations by test block. Panel b reports the reported difference together with the substitution contrast, the redevelopment contrast and the interaction, computed from unrounded saved predictions before display rounding. Blue marks the matched diagonal and orange marks the crossed evaluations.

In 2016 to 2017 the A pipeline loses 2.777 average precision points when only scoring inputs change, while the redevelopment contrast on A inputs is +4.945 points and the interaction contributes +0.671. The favorable total therefore comes from redeveloping the pipeline, and it stands alongside a scoring substitution that moves the metric in the opposite direction. In 2018 to 2019 the substitution and redevelopment contrasts are both positive, at approximately +1.367 and +1.432 points, and the interaction is small on this scale. In 2020 to 2021 direct substitution contributes only +0.112 points against +1.901 for redevelopment and -0.247 for the interaction. These are descriptive computational components rather than tests of differences among mechanisms.

The first block also measures how far the result moves with the parameter setting. Every original common fixed LightGBM candidate gives a negative diagonal difference there, at -4.571, -3.894, -1.979 and -0.071 points, and the later two blocks carry both signs across the same finite candidate set. The tuned result therefore combines version substitution with the candidates that selection chose, and reporting the four fixed configurations puts a number on that specification sensitivity.

Probability performance moves in a different direction from ranking performance. Tuned LightGBM Brier scores worsen from A to B in every block, and both arms sit above the constant reference in the last two blocks, where the constant score is 0.003847 against 0.007117 and 0.008345 for A and B. A ranking improvement and a probability comparison therefore support different statements about this cohort, and the ranking metric is the one used throughout. Absolute performance for the spline and random forest diagnostics, the calibration summaries and the four fixed candidate configurations are reported in the supplementary document, together with the conditional resampling intervals and the score and rank propagation checks.

## 4.2 Small development changes move the inference

Development influence and source evidence both shape how a contrast should be read. Deleting the mature members of the remaining unchanged negative group in 2018 to 2019 shifts the common fixed contrast by +11.420 points, which exceeds every one of the twenty matched ordinary draws for that group, while the two changed negative transition records produce changes inside the range of ordinary matched deletions in all blocks. In the final block, removing the sole unchanged transition positive shifts the contrast from -1.235 to -3.085 points, and eleven of the twenty ordinary matched positive deletions produce an absolute change at least as large. Figure 3 shows the transition deletions against the matched ordinary draws. No mature target is available for the unchanged positive in the first two blocks.

![](figures/figure3_development_influence.png){width=6.6in}

Figure 3. Development influence of selected observations against matched ordinary deletions. Diamonds mark the change in the common fixed LightGBM contrast after the indicated transition deletion, and gray points mark twenty prespecified ordinary matched deletions in the same block and group. Zero is the block baseline under full development, and all test observations remain intact. The comparison is descriptive, the draws do not equalize deleted design weight, and the point proportions are not p values.

Evaluation side influence is of the same order. Deleting one event linked cluster reduces the final tuned contrast from +1.766 to -0.080 points, which removes the positive difference and slightly crosses zero. That record has unchanged inputs in both arms and moves from risk rank four to risk rank one when the fitted pipeline changes, so the movement is consistent with fitted model propagation and an influential rare event rather than with a source error in the scored record.

## 4.3 The development domain dominates the reported contrast

Repeating the comparison under the size restriction separates development from evaluation, and the size restriction dominates the result in the middle block. Restricting only the evaluation sample leaves the contrast almost unchanged at +2.852 points against +2.846 under full development and evaluation. Developing on the size domain and evaluating the same restricted test set gives -16.009 points, with A at 31.976 and B at 15.966 percent average precision. The middle and right conditions are evaluated on identical observations, so the large negative value is a development domain effect rather than a composition change in the test set. Table 3 reports absolute performance, sample counts and event prevalence, and Figure 4 shows the three conditions for every block.

Table 3. Separating the size restriction on development from its restriction on evaluation.

{{TABLE_3}}

Note: Common fixed LightGBM is used throughout. Size means the consumer price index adjusted prediction origin asset threshold of 100 million 1980 US dollars. N and positives give unweighted test windows and positive windows, and Event % is the design weighted prevalence. Full development with a size restricted evaluation reuses the full development fitted pipelines, while the two size restricted conditions share the identical evaluation sample.

![](figures/figure4_development_domain.png){width=6.6in}

Figure 4. Development domain and evaluation domain under a size restriction. Bars report the common fixed LightGBM contrast BB - AA in average precision percentage points. The middle and right conditions in each block share the identical evaluation sample, so their difference isolates the changed development sample. Size is a prediction origin asset threshold of 100 million 1980 US dollars, which is a proxy for registry eligibility rather than a reconstruction of it.

The paired weight experiment distinguishes the same stages, as reported in the supplementary document. With frozen tuned pipelines and evaluation only perturbation, the LightGBM diagonal difference is positive in 98, 98 and 66 percent of the 200 draws. With development only perturbation the corresponding proportions are 48.5, 59.5 and 59.5 percent, and joint perturbation gives 50, 60 and 60 percent. Development only fifth to ninety fifth percentile ranges are -8.992 to +8.623, -11.858 to +16.057 and -7.085 to +7.972 average precision points, so the wide joint distribution accompanies substantial development sensitivity rather than being summarized by uncertainty in scoring a single fitted pair.

## 4.4 Exposure and disclosure timing

Later version availability is uneven across outcomes and horizons, which is why the version rule changes the evaluated population as well as the inputs. A later complete bundle exists for 80 of 188 positive windows against 4,048 of 5,314 other windows, an unweighted availability of 42.6 and 76.2 percent, and 73 of those 80 positive windows have a selected later source filed after the event, so the additional disclosure is largely contemporaneous with the outcome rather than predictive of it. Full cohort positive exposure counts are 108 without a bundle, 55 with unchanged later values and 25 with changed values, against 1,266, 2,766 and 1,282 for the remaining windows. Table 4 reports the composition by test block, and the exposure groups also differ in subsequent filing activity: among noncases, weighted annual filing continuity is 45.8, 68.8 and 64.5 percent across the no bundle, unchanged and changed groups, and among positive windows it is 10.2, 30.9 and 20.0 percent.

Table 4. Later version exposure by test block and recorded outcome.

{{TABLE_4}}

Note: Cells report unweighted counts with design weighted percentages within each block and outcome group. Event 1 is the directly linked registry target. Changed concerns any selected raw component above the stated tolerance, and rounding can prevent percentages from totaling 100.

Availability horizons show source replacement among already exposed observations as well as new exposure. Moving from a 90 day to a 365 day horizon adds 2,603 bundles and switches 136 existing later accessions, changing raw values for 801 landmarks. Moving from 365 to 730 days adds 1,301 bundles, switches 125 accessions and changes 484 landmarks. From 730 days to the latest rule seven bundles become newly available, thirteen existing accessions switch and ten landmarks change raw values, so the last contrast rests mainly on replacement among already exposed observations rather than on new exposure. The frozen adjacent reconstructions keep every selected source value identical when the selected accession is identical, which is an internal consistency check on the pipeline.

Relatively few latest development sources postdate model fitting: six, eight and six records, representing 0.216, 0.342 and 0.190 percent of development weight, and actual model inputs differ relative to the fit date selection for three, four and two records. The timing constraint still moves the metric: restricting development information to the fit date changes A scored average precision under common fixed LightGBM parameters, and it does so in different directions relative to original only training, as Table 5 reports. Most historical later disclosures were already known at fitting time, which is why the two information clocks are tracked separately: one clock governs what a development process may use and the other governs what a scoring exercise may use.

Table 5. Fixed LightGBM trained under different disclosure time rules and scored exclusively on original accession inputs.

{{TABLE_5}}

Note: The first three numeric columns report average precision percentages on the same original test inputs. The latest later version column uses the unlimited training source rule but scores the original version rather than the later version. Late counts refer to selected latest sources unavailable strictly before the test block fit date, and their weight share is measured in the mature development sample. These fixed parameter anchors differ from the tuned pipelines in Table 2 and were fitted separately from the version decomposition shown there.

## 4.5 Source evidence separates mechanisms by evidence level

The random test audit supports displayed asset agreement at all 24 sampled landmarks, and 95 of its 96 arm by component checks are display consistent, with one check recorded as unknown. Purposive development checks then identify a distinct mechanism behind each group, which is why the groups carry separate labels. Rentech explicitly reconciles understated tax liabilities in its later statements, including liabilities of 105.200 against 112.255 million dollars for December 2011. [@rentech2013revision] Silver Stream's transition statements reflect one continuing accounting entity, whereas the later comparison uses another after a reverse takeover, so its large asset difference is supported on both sides but concerns different reporting scope. [@silverstream2014transition; @silverstream2014annualAmendment] Gymboree, the sole positive transition landmark, has unchanged selected components in its 26 week transition report, so removing it changes development composition without removing a version difference in that record. [@gymboree2016transition; @gymboree2017quarterly]

The scale evidence is equally specific. The Nobilis filing states that its relevant financial statements are in thousands, which supports 22 scale keys spanning two period columns. [@nobilis2016_10k; @nobilis2017_10k] Those keys change only two main feature cells, both log assets, because uniform scaling cancels in the corresponding ratios. Four proposed sign replacements are classified as display and API differences, supported by concept definitions and taxonomy balance attributes, and reported as a sensitivity set beside the display supported keys. Table 6 reports both adjustment scenarios, and Figure 5 reports the evidence level reached by each class of adjustment.

Table 6. Tuned LightGBM under source supported and adjusted scenarios.

{{TABLE_6}}

Note: Scale supported applies 22 display supported scale keys and changes two feature cells. Scale plus disputed signs additionally imposes four sign proposals and changes six feature cells in total. The sensitivity scenario sets the display supported keys beside those four proposals, and the source ledger records the evidence that accompanies each one.

![](figures/figure5_source_evidence.png){width=6.6in}

Figure 5. Evidence level and model consequence of the source adjustments. Panel a reports the number of source keys or checks that reached each evidence level. Panel b reports the tuned LightGBM contrast under the unadjusted, scale supported and combined scenarios. Scale supported keys leave every tuned and fixed LightGBM test prediction exactly unchanged, so the combined scenario is not evidence about the effect of certified input errors.

This trace is more informative than treating 22 source keys as 22 independently changed predictive observations, and it separates a documented scale property from a sign question that the display evidence leaves open. Two conclusions follow. First, the combined scenario changes test predictions, so the disputed items enter a development block and the sensitivity scenario is reported as a substantive case rather than a presentation detail. Second, the scale scenario leaves every LightGBM prediction identical while logistic predictions move slightly, with maximum individual probability changes of 0.002534 in tuned comparisons and 0.001826 under common fixed parameters, which separates a documented scale property from a sign question that the display evidence leaves open. A source key to component to feature to stage ledger accompanies the saved predictions and is retained in the reproducibility package.

# 5 Discussion

## 5.1 Implications for model validation practice

The decomposition is accounting, and the empirical results supply its content: a favorable reported difference, a substitution contrast of the opposite sign, a development domain that changes a version contrast by more than ten points, and a single development observation that reverses a block conclusion. For a validator, the practical implication is that a validation report which records only an extraction date and a train and test split leaves the largest source of a version related result unspecified. Seven practices follow directly from the results and from the design of the protocol.

1. Freeze model input provenance together with observation dates, and record the accession or source rule that determines each historical predictor value.
2. Separate redevelopment from rescoring whenever the version rule changes, so that each route receives its own contrast.
3. Validate the fit time and score time information sets as two separate clocks, so that a revision disclosed before fitting counts for development and a later scoring input counts for evaluation.
4. Evaluate on the full observation set, because conditioning on the availability of a later version changes the evaluated population and, in this cohort, is related to the outcome.
5. Retain observations whose inputs are unchanged, because a change in the fitted pipeline still moves their scores and ranks.
6. Report a fixed parameter benchmark alongside independently tuned pipelines, so that the reader sees the specification range that the four finite configurations span.
7. Trace material numerical discrepancies back to source records before naming a mechanism, and label each one by its evidence level.

## 5.2 Data versioning as a governance risk

Financial input versioning is a governance issue rather than a refresh problem. A model that is nominally unchanged is evaluated on a different historical information set after a database refresh, and the required disclosures for credit risk models place data quality and the documentation of model inputs inside the validation obligation. [@sr1107; @bcbs2016; @ecb_internal_models] The results here specify what such documentation contains for a version rule to be auditable: the accession or source selection rule, the disclosure time boundary used at fitting, the scoring time boundary used at evaluation, the missingness mask, and the set of observations deleted or retained by the rule. A validation report becomes reproducible when it records the version rule as well as the retrieval date, because the same pipeline evaluated on the same observations produces different numbers after the underlying values change.

Model risk management also distinguishes the risk of an incorrect model from the risk of incorrect use, and version selection sits between those categories: a version rule can be defensible as a data decision and still shift a validation outcome away from the deployed pipeline. The protocol measures that shift.

Source evidence is separate from arithmetic. Independent code recomputes the four cell metrics from saved predictions to numerical precision, separate checks reconstruct saved development control predictions and verify fit date source restrictions, and source checks consult statements outside the stored numerical path while preserving retrieval and authentication limits. Financial comparability requires more than numerical alignment: a documented correction and a change of accounting predecessor both satisfy the same concept and period rules while implying different economic meanings, as the scope examples in this cohort show. [@rcs2014_10k; @rcs2015_10ka; @americanhealthcarereit2022] Every arm by component check in this audit reached the displayed statement level, and the protocol therefore reports each difference at the evidence level it reached: a difference consistent with a displayed statement is a supported measurement, and the source ledger records which context and presentation evidence accompanies it. The measured quantities are the two contrasts, the domain effects and the source classifications reported above, and the protocol applies to any cohort for which a version rule and a documented pipeline can be reconstructed.

## 5.3 Scope and next steps

The scope of these results is the stated application and the stated evidence base, and four properties define it. The target is a directly linked large company registry event, so the numbers describe that registry definition. Source accessibility excludes part of the historical frame, so the cohort is the accessible domain summarized in Table 1. Later disclosure availability is related to the outcome, which is why the evaluation sample stays complete. The earliest validation stage carries three positive preliminary training windows and seven positive validation windows, and the matched ordinary deletion exercise uses twenty draws per eligible comparison.

The protocol applies without change to a second extraction path for the same filings, which tests measurement reproducibility, and to a cohort with a longer version history, which tests predictive transportability.

# 6 Conclusion

Financial data versioning is an input data risk that enters model validation through three routes: substitution of scoring inputs, redevelopment of the fitted pipeline and selection of the evaluated population. Crossing the two versions on identical observations separates those routes, and in this application the routes differ in direction and magnitude. Independently tuned pipelines improved on the diagonal in every block, the direct substitution contrast ran from -2.777 points in the first block to +0.112 in the last, a development domain restriction moved a contrast from +2.852 to -16.009 average precision points while the evaluation sample stayed fixed, and removing one development observation changed a block conclusion. Version selection therefore belongs in the validation record alongside the extraction date, and every validation result is conditional on the version rule that produced it. The crossed version protocol makes that condition measurable and reportable.

# Data and code availability

The analysis code, frozen derived analysis inputs, component lineage, configurations, saved predictions, source status tables and an executable offline numerical audit are openly available, archived at https://doi.org/10.5281/zenodo.22977363, together with the figures, tables and the LaTeX source of this paper. Scripts regenerate every reported display from the frozen result files. Access paths for the public financial data sources are documented, and redistribution of original source records follows their respective terms.

# AI assistance

OpenAI Codex was used only for limited Python code assistance and English language polishing. All substantive research tasks, including study design, data collection and processing, analysis, interpretation, and manuscript preparation, were performed by the authors. AI did not generate or alter data or determine conclusions, and the authors take full responsibility for the manuscript.

# References

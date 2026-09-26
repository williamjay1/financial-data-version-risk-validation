# Read-only source, literature and interpretation review

Reviewed manuscript: `revision_20260922_round2/manuscript/manuscript.md`, SHA256 `3fe5c9f8289348efbb1c8ecfbe06e0138b3c5a7bb8b9071788cfcc388d5be7df`. Review date: 2026-09-23. This check did not edit the manuscript, old data, models or source records, and did not fit a model. It is an AI-assisted review, not human accounting sign-off.

## Decision

No newly identified fatal or major source, citation or interpretation error in the reviewed version. The manuscript is a deliverable research draft. Submission remains CONDITIONAL: consequential source judgments and accountability need author confirmation; original issuer instance/context/presentation chains remain unauthenticated; there is no independent prediction sample. These boundaries are now stated explicitly rather than represented as completed work. This review does not certify journal acceptance or independently prove the method's novelty.

## Findings requiring precision

1. **Minor scope ambiguity, §4.3, line 190.** The sentence “Removing the two changed negative transition records produces changes within the range of ordinary matched deletions in all blocks” should explicitly retain the learner restriction. The immediately preceding sentence concerns common fixed LightGBM, for which the claim is supported. It is not a learner-general result: for LR in 2016–2017, the transition change is approximately 0.000013896 in AP units, above the ordinary signed range's upper endpoint of approximately 0.000004224. Suggested replacement: **“For LightGBM, removing the two changed negative transition records produces changes within the range of ordinary matched deletions in all three blocks.”** No substantive conclusion needs to change. Evidence: `results/development_controls/matched_deletion_comparison.csv`, group `changed_negative`.

2. **Minor stage precision, §4.3, line 196.** “Removing it changes development composition...” accurately describes the development-only Gymboree control. That landmark also appears as a first-block test observation, so the sentence can be even clearer without inviting a general deletion claim. Optional replacement: **“In the development-only control, removing this matured observation changes development composition without removing a version difference in that record.”** The Figure 3 caption already says test observations remain intact; this is a clarity improvement, not a factual contradiction.

3. **Minor layout, render pages 11–12.** Figure 3 is intact but its caption continues with two lines at the top of page 12. Prefer keeping the caption with its figure if this can be achieved without compressing labels or creating a large gap. There is no truncation or missing content. The remaining pages inspected have no blocking layout problem.

The earlier proposed correction to §2.3 is resolved: line 73 now says **“No original issuer XBRL instance, context and presentation chain has been authenticated in this audit. Human accounting sign-off remains pending.”** This accurately records zero authenticated issuer chains without ambiguity.

## Source keys, features and interpretation

- Twenty-two Nobilis keys are source-component-period keys, not 22 independent observations or 22 main predictive features. Their main A/B effect is two `log_assets` feature cells; uniform scaling cancels the relevant ratios. The manuscript and Table 6 note reflect this correctly. C-arm changes are not misrepresented as main A/B effects.
- The additional four sign proposals remain unresolved display/API discrepancies. The combined 26-key scenario changes six main A/B feature cells, but neither that count nor the sensitivity run authenticates the original issuer XBRL. The manuscript no longer attributes its changed LightGBM results to a certified correction set.
- The scale-only LightGBM test predictions remain exactly unchanged for both the tuned and common-fixed implementations in the saved evidence. LR changes are small and explicitly reported. Do not restore the earlier claim that known source corrections materially changed LightGBM: the changed LightGBM results accompany the disputed signs.
- Rentech's documented tax-payable revision and Silver Stream's changed reporting scope are separated. Gymboree and RTW are explicitly unchanged in the selected A/B inputs; their fitted-model influence does not imply an error in their source record. RCS common-control recasting and American Healthcare REIT reverse acquisition are scope examples, not universal explanations of all numerical changes.
- Random test audit: 24 sampled landmarks, assets in both arms, 96 component-arm checks, 95 display-consistent and one unknown. Purposive additions are not used to infer an error prevalence. The text distinguishes display checks from original-instance authentication and independent human certification.

## Four cells, ordinary perturbations and independence

The four-cell AP decomposition is presented as an algebraic, procedural comparison. It is not called a causal mechanism test, and the fitted and scored-input contrasts are not presumed to have the same sign. Separately tuned and fixed runs are identified; the tuned positive diagonal result is not generalized to fixed hyperparameters. The small first-block tuning/validation event counts, poorer Brier outcomes and ordinary-development sensitivity remain visible.

Ordinary matched deletion proportions are not treated as p values or randomization inference. The manuscript retains the exceptional unchanged-negative subgroup and the unmatched removed negative weight mass, so it does not dismiss all transition-related sensitivity as routine noise. Weight perturbation quantiles are not future-population confidence intervals or additive variance components.

The distinction between arithmetic recomputation, saved-model reconstruction, source checks outside companyfacts, an independent measurement route, and a new prediction sample is explicit. No extra source check is presented as a new test cohort. Temporal fit-date restrictions use present accession-associated records and do not certify historical API snapshots.

## Literature and source positioning

The closest direct original/restated-input precedent is correctly identified as **Hashemi and Jonsson (2017), a master's thesis**, not a journal article. It used 52 screened firms and fixed risk formulas; the present manuscript does not claim that comparing original with restated accounting inputs is a new idea. Its distinction is the implemented evaluation design and its evidence, with limitations preserved.

The final **Zhang et al. (2026), Risks 14(8), 179** is cited with five authors and described using the published paper, not obsolete preprint limitations. Its filing/accession/report-date alignment and inflation-adjusted size rule are acknowledged. Mattos and Shasha's low-quality financial-data problem, the realistic delayed-discovery evaluation work and Yang and Zhu's detection-lag study are not misrepresented as solving exactly this versioned bankruptcy experiment. These comparisons support a bounded contribution; they do not establish absolute priority or a universal benefit from revisions.

## Table 6 first-block independent check

The following values were recomputed directly from three saved metrics tables. Percentages and percentage-point differences below retain more digits than the manuscript; all three tuned rows round to the printed table. The fixed rows are shown only to rule out mixing the experiment variants.

| Input scenario | Regime | AA AP % | BB AP % | BB−AA pp |
|---|---|---:|---:|---:|
| Unadjusted | Tuned | 24.746861983474 | 27.585981990117 | +2.839120006643 |
| Scale supported | Tuned | 24.746861983474 | 27.585981990117 | +2.839120006643 |
| Scale + disputed signs | Tuned | 25.859780723796 | 28.435983366447 | +2.576202642651 |
| Unadjusted | Fixed | 24.746861983474 | 20.175951569110 | −4.570910414364 |
| Scale supported | Fixed | 24.746861983474 | 20.175951569110 | −4.570910414364 |
| Scale + disputed signs | Fixed | 25.859780723796 | 20.485901244149 | −5.373879479647 |

Machine-readable evidence with metrics-source hashes: `table6_firstblock_independent_check.csv`. Table 6 is explicitly tuned, so its positive first-block contrast is not inconsistent with the negative fixed comparison elsewhere.

## Author-confirmation interface and visual coverage

`author_pending_all_consequential_sources.csv` consolidates 59 existing source-component-arm checks: 22 Nobilis scale keys, four unresolved signs, 21 new targeted display checks and 12 reused targeted checks. It covers Nobilis plus all six requested mechanism/influence companies, preserves evidence URLs/locators and stage links, and leaves every author signature, identity, date and decision blank. It is not 59 independent companies or human confirmations. The accompanying README explains the evidence hierarchy.

Actual PNG inspection completed for **pages 10, 11, 12, 13, 14, 15, 16, 17 and 18** of `qa/main_final/Financial_Data_Version_Evaluation.pdf`, SHA256 `77b4a16fe189758878f0df1a7ba3015766dca38c19bc825dbb5014758fc53453`. All images were opened and viewed, rather than judged from extracted text. Table 6 is complete on one page; figures have legible labels without overlap; reference URLs and footers are within the visible page; no blank extra page appears. Per-page findings and PNG hashes are in `visual_review.json`. Pages 1–9 belong to the parent's separate review and are not claimed here.


## Final render follow-up

The main_verified render was compared by SHA256 with the previously viewed main_final PNGs. Only pages 11 and 12 changed within this reviewer’s pages 10–18; both were actually reopened and visually inspected. The LightGBM qualifier is present. Figure 3 and its complete caption now occupy page 12 without truncation or overlap. Pages 10 and 13–18 are byte-identical to the previously inspected images. There are no remaining layout issues in these pages. Updated PDF SHA256: `3210b32b919d4ce09ad781d6247db18ccf3ce194a5357b993616e50a9a96dd1e`. All current page hashes and inspection bases are in `visual_review.json`.

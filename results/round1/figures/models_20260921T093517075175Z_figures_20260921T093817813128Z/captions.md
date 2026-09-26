# Figure titles and captions

Figure 1. Annual analysis sample.
(A) The sum of inverse cluster inclusion probabilities over eligible filing landmarks,
by decision year. This estimates landmark counts in the restricted historical filing
domain; it is not a count of independent companies. (B) Unweighted registry-linked
positive 365-day filing windows and distinct directly linked CIKs contributing at
least one such window in that decision year. A CIK can contribute in more than one
year. Neither series is a count of independent bankruptcy episodes or complete
market bankruptcies. The two panels have separate count scales. Reporting eligibility
and the original-accession positive-assets condition apply to the full frozen cohort.

Figure 2. Changes in financial model inputs.
For each of ten inputs, bars show the inverse-probability-weighted proportion of
initially observed values that change between original-accession version A and
coherent later-accession version B. A numerical change satisfies
abs(A−B) > 10⁻¹² × max(1, abs(A), abs(B)). Initial missing values remain missing and
are excluded from the feature-specific primary denominator; all-cohort denominators,
raw counts and weighted counts are exported separately. These are changes in model
inputs, including ratios, rather than counts of altered raw financial facts.
The figure contains only the coherent A/B comparison.
Reporting lag, a common model covariate, is not one of the ten vintage-varying inputs.
These are accession-specific records reconstructed from the retrieved SEC API;
neither version is claimed to be an authenticated historical API snapshot.

Figure 3. Paired changes in weighted average precision.
(A) B-trained/B-input predictions minus A-trained/A-input predictions, separately
for logistic regression (LR) and LightGBM (LGBM) in each test block. (B) The same
input contrast with the final A estimator and A preprocessing held fixed, requiring
no additional training. Points and intervals are in percentage points (100 times
the difference on the average-precision probability scale); positive values indicate
higher retrospective average precision for B. Lines are basic centered 95% design
bootstrap intervals from 1000 Rao–Wu–Yue rescaled SRS replicates, with
finite population correction. All 1000 sampled noncase
clusters, including clusters with no eligible test landmarks, enter the resampling
design; 383 certainty clusters remain fixed. The same cluster
replicate weights preserve pairing across versions, learners and test blocks.
The intervals condition on the fitted models, observed registry outcomes, certainty
clusters and the finite sampling frame. They do not include model training or
selection variability, registry undercoverage, uncertainty in the case population,
or future macroeconomic variation. The three blocks are not independent economic
experiments. No multiple-comparison or simultaneous-coverage claim is made. Invalid
replicate rates and point-estimate denominators are retained in the exported data;
an unavailable interval is never replaced with zero. B uses later information and
is a diagnostic comparison, not a deployable forecasting procedure.

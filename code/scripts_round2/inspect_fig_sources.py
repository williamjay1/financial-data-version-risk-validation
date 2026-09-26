"""Print the column interfaces of the frozen outputs used by the figure builder."""
import pandas as pd
E='revision_20260922_round2/results/evaluation_diagnostics/'
D='revision_20260922_round2/results/development_controls/'
for name in ['raw_component_magnitude_summary.csv','raw_component_sign_categories.csv',
             'version_exposure_summary.csv','adjacent_horizon_summary.csv',
             'perturbation_modes_all_replicates.csv']:
    z=pd.read_csv(E+name)
    print('==',name,z.shape)
    print(z.columns.tolist())
    print(z.head(3).to_string())
    print()
for name in ['deletion_AP_changes.csv','matched_deletion_comparison.csv','CPI_domain_diagonal.csv','four_candidate_LGBM_AP.csv']:
    z=pd.read_csv(D+name)
    print('==',name,z.shape)
    print(z.columns.tolist())
    print(z.head(3).to_string())
    print()

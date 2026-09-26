import pandas as pd
R = 'revision_20260922_round2/results/'
f = pd.read_csv(R + 'fit_date/fit_date_comparisons.csv')
print(f.columns.tolist())
print(f[f.metric == 'average_precision'].to_string())
c = pd.read_csv(R + 'fit_date/fit_date_coverage.csv')
print(c.columns.tolist())
print(c.to_string())

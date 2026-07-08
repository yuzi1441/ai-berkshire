import pandas as pd, json, os
base='data/hengrui'
for name in ['indicator_em','profit_em','balance_em','cash_em','abstract_sina','analysis_sina']:
 print('\n###', name)
 df=pd.read_csv(f'{base}/{name}.csv')
 print('shape',df.shape)
 print(list(df.columns)[:80])
 print(df.head(3).to_string(max_cols=25))

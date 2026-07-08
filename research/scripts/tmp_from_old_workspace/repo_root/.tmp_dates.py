import pandas as pd
for name in ['profit_em','balance_em','cash_em']:
 df=pd.read_csv(f'data/hengrui/{name}.csv')
 print('\n',name)
 print(df[['REPORT_DATE','REPORT_TYPE','REPORT_DATE_NAME']].head(12).to_string(index=False))

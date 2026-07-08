import pandas as pd, glob, os
for f in glob.glob('sources/*.csv'):
    df=pd.read_csv(f)
    print('\nFILE', os.path.basename(f), 'shape', df.shape)
    print('cols containing report/date/name/revenue/income/profit/cash/dividend/operate/power:')
    cols=[c for c in df.columns if any(k in c.lower() for k in ['report','date','name','income','profit','cash','div','operate','revenue','roe','asset','liab','eps'])]
    print(cols[:120])
    print(df[[c for c in ['REPORT_DATE','REPORT_DATE_NAME','NOTICE_DATE','TOTAL_OPERATE_INCOME','OPERATE_INCOME','PARENT_NETPROFIT','NETPROFIT','NETCASH_OPERATE','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','BASIC_EPS','ROE_WEIGHT'] if c in df.columns]].head(12).to_string(index=False))
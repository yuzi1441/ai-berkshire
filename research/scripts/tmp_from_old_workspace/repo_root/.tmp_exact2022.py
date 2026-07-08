import pandas as pd, json
for name in ['indicator_em','profit_em','balance_em','cash_em']:
    df=pd.read_csv(f'data/hengrui/{name}.csv')
    row=df[df.REPORT_DATE_NAME=='2022年报'].iloc[0]
    print(name)
    for c in ['TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','NETCASH_OPERATE','TOTAL_ASSETS','TOTAL_PARENT_EQUITY']:
        if c in row.index: print(c, repr(row[c]))

import pandas as pd
for fn in ['data/lianying_indicator_按报告期.csv','data/lianying_profit.csv','data/lianying_balance.csv','data/lianying_cash.csv']:
    print('\n###',fn)
    df=pd.read_csv(fn)
    print('shape',df.shape)
    print(list(df.columns)[:120])
    # print selected first rows with important columns
    for cols in [['REPORT_DATE','REPORT_DATE_NAME','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','XSMLL','ROEJQ','EPSJB','BPS','MGJYXJJE'],
                 ['REPORT_DATE','TOTAL_OPERATE_INCOME','OPERATE_INCOME','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','OPERATE_COST','RESEARCH_EXPENSE'],
                 ['REPORT_DATE','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','MONETARYFUNDS','ACCOUNTS_RECE','INVENTORY','CONTRACT_LIAB'],
                 ['REPORT_DATE','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CCE_ADD','SALES_SERVICES']]:
        exists=[c for c in cols if c in df.columns]
        if exists:
            print(df[exists].head(8).to_string())
            break

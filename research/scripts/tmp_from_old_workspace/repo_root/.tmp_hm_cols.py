import pandas as pd, pathlib, json, math
base=pathlib.Path('reports/华明装备/sources/eastmoney')
profit=pd.read_csv(base/'profit_em.csv')
bal=pd.read_csv(base/'balance_em.csv')
cf=pd.read_csv(base/'cashflow_em.csv')
# list likely columns
for name,df,terms in [('profit',profit,['INCOME','COST','PROFIT','RESEARCH','SALE','MANAGE','OPERATE_PROFIT']),('balance',bal,['MONETARY','CASH','NOTE','RECEIV','INVENT','LOAN','BORROW','PAYABLE','TOTAL_ASSETS','TOTAL_LIAB','TOTAL_EQUITY','INTANGIBLE']),('cashflow',cf,['NETCASH','OPERATE','INVEST','FINANCE','CASH'])]:
    print('\n---',name,'---')
    cols=[]
    for c in df.columns:
        if any(t in c.upper() for t in terms): cols.append(c)
    print(cols[:120])
    print(df[['REPORT_DATE','REPORT_DATE_NAME']+[c for c in cols[:20] if c in df.columns]].head(6).to_string())

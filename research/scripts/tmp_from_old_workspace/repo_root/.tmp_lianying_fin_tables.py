import pandas as pd, json
ind=pd.read_csv('data/lianying_indicator_按报告期.csv')
profit=pd.read_csv('data/lianying_profit.csv')
bal=pd.read_csv('data/lianying_balance.csv')
cash=pd.read_csv('data/lianying_cash.csv')
# annual rows
for df,name,cols in [
(ind,'ind',['REPORT_DATE_NAME','TOTALOPERATEREVE','TOTALOPERATEREVETZ','PARENTNETPROFIT','PARENTNETPROFITTZ','KCFJCXSYJLR','KCFJCXSYJLRTZ','XSMLL','ROEJQ','EPSJB','BPS','MGJYXJJE','ZCFZL','ROIC','FCFF_BACK','FCFF_FORWARD']),
(profit,'profit',['REPORT_DATE_NAME','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','TOTAL_OPERATE_COST','SALE_EXPENSE','MANAGE_EXPENSE','RESEARCH_EXPENSE','ME_RESEARCH_EXPENSE','OPERATE_PROFIT','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS']),
(bal,'bal',['REPORT_DATE_NAME','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','PARENT_EQUITY','MONETARYFUNDS','TRADE_FINASSET_NOTFVTPL','ACCOUNTS_RECE','NOTE_ACCOUNTS_RECE','INVENTORY','CONTRACT_ASSET','CONTRACT_LIAB','FIXED_ASSET','INTANGIBLE_ASSET','GOODWILL','SHORT_LOAN','LONG_LOAN','BOND_PAYABLE']),
(cash,'cash',['REPORT_DATE_NAME','SALES_SERVICES','TOTAL_OPERATE_INFLOW','TOTAL_OPERATE_OUTFLOW','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CONSTRUCT_LONG_ASSET','CCE_ADD','END_CCE','NETPROFIT','FA_IR_DEPR','IA_AMORTIZE'])
]:
    ex=[c for c in cols if c in df.columns]
    annual=df[df['REPORT_DATE_NAME'].astype(str).str.contains('年报|一季报', regex=True, na=False)][ex].head(12)
    print('\n###',name)
    print(annual.to_string(index=False))
# Find actual likely columns for balance names
print('\nBalance cols containing MONEY/CASH/FUND/ASSET/LIAB INVENTORY CONTRACT RECE:')
print([c for c in bal.columns if any(s in c for s in ['MONET','CASH','ASSET','LIAB','INVENTORY','CONTRACT','RECE','PAYABLE','EQUITY'])][:200])

import pandas as pd, re, json, math
from pathlib import Path
base=Path('data')
prof=pd.read_csv(base/'tmp_cypc_stock_profit_sheet_by_report_em.csv')
cf=pd.read_csv(base/'tmp_cypc_stock_cash_flow_sheet_by_report_em.csv')
bal=pd.read_csv(base/'tmp_cypc_stock_balance_sheet_by_report_em.csv')
ind=pd.read_csv(base/'tmp_cypc_stock_financial_analysis_indicator.csv')
div=pd.read_csv(base/'tmp_cypc_stock_dividend_cninfo.csv')

def annual(df):
    x=df[df['REPORT_TYPE'].astype(str).eq('年报')].copy()
    x['year']=pd.to_datetime(x['REPORT_DATE']).dt.year
    return x.sort_values('year', ascending=False)
pa=annual(prof); ca=annual(cf); ba=annual(bal)
cols_p=['REPORT_DATE','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','OPERATE_EXPENSE','SALE_EXPENSE','MANAGE_EXPENSE','RESEARCH_EXPENSE','FINANCE_EXPENSE','INVEST_INCOME','OPERATE_PROFIT','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS']
cols_c=['REPORT_DATE','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CONSTRUCT_LONG_ASSET','CASH_PAY_ACQ_CONST_FIOLTA']
# Some names contain BUY_FIXED_ASSET? print all cash cols containing CONSTRUCT/CASH_PAY
print('CF cols', [c for c in cf.columns if any(k in c for k in ['CONSTRUCT','CONST','FIXED','LONG_ASSET','NETCASH'])][:80])
cols_b=['REPORT_DATE','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_PARENT_EQUITY','MONETARYFUNDS','LONG_EQUITY_INVEST','FIXED_ASSET','CIP','LONG_LOAN','BOND_PAYABLE','SHORT_LOAN','NONCURRENT_LIAB_1YEAR','SHARE_CAPITAL']
print('\nPROFIT annual')
print(pa[[c for c in cols_p if c in pa.columns]].head(8).to_string(index=False))
print('\nCF annual')
print(ca[[c for c in cols_c if c in ca.columns]].head(8).to_string(index=False))
print('\nBAL annual')
print(ba[[c for c in cols_b if c in ba.columns]].head(8).to_string(index=False))
print('\nIndicator latest rows')
print(ind.tail(8)[['日期','摊薄每股收益(元)','加权每股收益(元)','每股经营性现金流(元)','加权净资产收益率(%)','资产负债率(%)','总资产(元)']].to_string(index=False))
print('\nDividend tail')
print(div.tail(10).to_string(index=False))

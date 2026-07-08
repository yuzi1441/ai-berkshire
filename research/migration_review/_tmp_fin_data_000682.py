import akshare as ak, pandas as pd, json, pathlib, math
pd.set_option('display.max_columns',100); pd.set_option('display.width',300)
out=pathlib.Path('data/oriental_electronics'); out.mkdir(parents=True,exist_ok=True)
# fetch abstract
absdf=ak.stock_financial_abstract(symbol='000682')
absdf.to_csv(out/'financial_abstract_000682.csv',index=False,encoding='utf-8-sig')
# select important rows and dates
cols=['指标','20260331','20251231','20241231','20231231','20221231','20211231']
want=['营业总收入','归母净利润','扣非净利润','经营现金流量净额','基本每股收益','每股净资产','净资产收益率ROE','销售毛利率','销售净利率','资产负债率','总资产周转率','应收账款周转率','存货周转率']
sel=absdf[absdf['指标'].astype(str).isin(want)][[c for c in cols if c in absdf.columns]]
print('ABSTRACT')
print(sel.to_string(index=False))
# statements
for name,fn in [('profit',ak.stock_profit_sheet_by_report_em),('balance',ak.stock_balance_sheet_by_report_em),('cashflow',ak.stock_cash_flow_sheet_by_report_em)]:
    df=fn(symbol='SZ000682')
    df.to_csv(out/f'{name}_em_SZ000682.csv',index=False,encoding='utf-8-sig')
    print('\n',name,df.shape)
    print(df[['REPORT_DATE_NAME','REPORT_DATE'] + [c for c in df.columns if c in ['TOTAL_OPERATE_INCOME','OPERATE_INCOME','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','NETPROFIT','TOTAL_OPERATE_COST','OPERATE_COST','OPERATE_PROFIT','TOTAL_PROFIT','BASIC_EPS','WEIGHTAVG_ROE','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','MONETARYFUNDS','ACCOUNTS_RECE','INVENTORY','TOTAL_OPERATE_OUTFLOW','NETCASH_OPERATE','NETCASH_INVEST','CONSTRUCT_LONG_ASSET','NETCASH_FINANCE']]].head(8).to_string(index=False))

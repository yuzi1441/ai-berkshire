import akshare as ak
import pandas as pd
sym='SZ300760'
for name, func in [('profit',ak.stock_profit_sheet_by_report_em),('balance',ak.stock_balance_sheet_by_report_em),('cash',ak.stock_cash_flow_sheet_by_report_em)]:
    df=func(symbol=sym)
    print('\n###',name, df.shape)
    cols=['REPORT_DATE','REPORT_TYPE','REPORT_DATE_NAME','TOTAL_OPERATE_INCOME','OPERATE_INCOME','OPERATE_COST','SALE_EXPENSE','MANAGE_EXPENSE','RESEARCH_EXPENSE','ME_RESEARCH_EXPENSE','OPERATE_PROFIT','TOTAL_PROFIT','NETPROFIT','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','BASIC_EPS','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_EQUITY','PARENT_EQUITY','MONETARYFUNDS','TOTAL_CURRENT_ASSETS','TOTAL_CURRENT_LIAB','INVENTORY','ACCOUNTS_RECE','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CONSTRUCT_LONG_ASSET']
    use=[c for c in cols if c in df.columns]
    print(df[use].head(10).to_string(index=False))

print('\n### zygc')
df=ak.stock_zygc_em(symbol=sym)
print(df.head(30).to_string(index=False))
print(df.columns.tolist(), df.shape)

print('\n### info')
df=ak.stock_individual_info_em(symbol='300760')
print(df.to_string(index=False))

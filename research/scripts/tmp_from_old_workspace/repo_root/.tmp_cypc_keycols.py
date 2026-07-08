import pandas as pd, glob
for f in ['data/tmp_cypc_stock_profit_sheet_by_report_em.csv','data/tmp_cypc_stock_cash_flow_sheet_by_report_em.csv','data/tmp_cypc_stock_balance_sheet_by_report_em.csv','data/tmp_cypc_stock_financial_analysis_indicator.csv','data/tmp_cypc_stock_dividend_cninfo.csv']:
 print('\n###',f)
 df=pd.read_csv(f)
 print('shape',df.shape)
 # date col
 datecol = 'REPORT_DATE' if 'REPORT_DATE' in df.columns else ('日期' if '日期' in df.columns else df.columns[0])
 print('dates', df[datecol].head(12).to_list())
 cols=[]
 for c in df.columns:
     if any(k in c for k in ['TOTAL_OPERATE_INCOME','OPERATE_INCOME','PARENT_NETPROFIT','NETPROFIT','OPERATE_PROFIT','TOTAL_PROFIT','BASIC_EPS','ROE','TOTAL_ASSETS','TOTAL_LIABILITIES','TOTAL_PARENT_EQUITY','NETCASH_OPERATE','NETCASH_INVEST','NETCASH_FINANCE','CONSTRUCT','CASH_PAY_ACQ','固定资产','每股经营','资产负债率','销售毛利率','加权净资产收益率','股息','派息','报告期']):
         cols.append(c)
 print('matched cols', cols[:80])
 print(df[[datecol]+cols[:20]].head(8).to_string())

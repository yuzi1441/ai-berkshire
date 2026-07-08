import akshare as ak, pandas as pd, json
pd.set_option('display.max_columns', None); pd.set_option('display.width', 220); pd.set_option('display.max_colwidth', 80)
code='002463'
print('---basic info---')
try:
 print(ak.stock_individual_info_em(symbol=code).to_string(index=False))
except Exception as e: print('ERR basic', type(e).__name__, e)
print('---spot row---')
try:
 spot=ak.stock_zh_a_spot_em()
 row=spot[spot['代码'].astype(str)==code]
 print(row.to_string(index=False))
except Exception as e: print('ERR spot', type(e).__name__, e)
print('---hist recent---')
try:
 hist=ak.stock_zh_a_hist(symbol=code, period='daily', start_date='20260620', end_date='20260706', adjust='')
 print(hist.tail(10).to_string(index=False))
except Exception as e: print('ERR hist', type(e).__name__, e)
print('---profit columns and latest---')
try:
 prof=ak.stock_profit_sheet_by_report_em(symbol='SZ'+code)
 print(prof.columns.tolist())
 print(prof.head(8).to_string(index=False))
 prof.to_csv('data/hudian_profit_em.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR prof', type(e).__name__, e)
print('---balance latest---')
try:
 bal=ak.stock_balance_sheet_by_report_em(symbol='SZ'+code)
 print(bal.columns.tolist())
 print(bal.head(5).to_string(index=False))
 bal.to_csv('data/hudian_balance_em.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR bal', type(e).__name__, e)
print('---cash latest---')
try:
 cf=ak.stock_cash_flow_sheet_by_report_em(symbol='SZ'+code)
 print(cf.columns.tolist())
 print(cf.head(5).to_string(index=False))
 cf.to_csv('data/hudian_cashflow_em.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR cf', type(e).__name__, e)
print('---financial indicators sina latest---')
try:
 ind=ak.stock_financial_analysis_indicator(symbol=code, start_year='2020')
 print(ind.columns.tolist())
 print(ind.tail(10).to_string(index=False))
 ind.to_csv('data/hudian_indicator_sina.csv', index=False, encoding='utf-8-sig')
except Exception as e: print('ERR ind', type(e).__name__, e)

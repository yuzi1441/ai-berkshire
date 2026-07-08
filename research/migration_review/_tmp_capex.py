import akshare as ak, pandas as pd
pd.set_option('display.max_rows', 80)
try:
 df=ak.stock_financial_report_sina(stock='sh688271', symbol='现金流量表')
 print(df.head(30).to_string())
 df.to_csv('reports/联影医疗/sources/sina_cashflow.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR',type(e).__name__,e)

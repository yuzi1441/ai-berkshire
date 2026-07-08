import akshare as ak, pandas as pd, pathlib, json
out=pathlib.Path('sources')/'东方电子'
try:
 df=ak.stock_financial_abstract(symbol='000682')
 df.to_csv(out/'akshare_东方电子_财务摘要.csv',index=False,encoding='utf-8-sig')
 need=['归母净利润','营业总收入','扣非净利润','经营现金流量净额','资产总计','归属母公司股东权益合计','基本每股收益','每股净资产']
 cols=['选项','指标','20260331','20251231','20250331','20241231']
 print(df[df['指标'].isin(need)][cols].to_string(index=False))
except Exception as e: print('ERR abs',e)
try:
 df=ak.stock_financial_report_sina(stock='sz000682', symbol='资产负债表')
 print('sina bs',df.shape,df.head().to_string())
 df.to_csv(out/'sina_东方电子_资产负债表.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR sina bs',repr(e))
try:
 df=ak.stock_financial_report_sina(stock='sz000682', symbol='利润表')
 print('sina is',df.shape,df.head().to_string())
 df.to_csv(out/'sina_东方电子_利润表.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR sina is',repr(e))
try:
 df=ak.stock_financial_report_sina(stock='sz000682', symbol='现金流量表')
 print('sina cf',df.shape,df.head().to_string())
 df.to_csv(out/'sina_东方电子_现金流量表.csv',index=False,encoding='utf-8-sig')
except Exception as e: print('ERR sina cf',repr(e))
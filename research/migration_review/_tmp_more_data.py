import pathlib, pandas as pd, akshare as ak, requests, re, json
src=pathlib.Path('reports/联影医疗/sources')
# Balance sheet selected
try:
 b=ak.stock_financial_report_sina(stock='sh688271', symbol='资产负债表')
 b.to_csv(src/'sina_balance.csv',index=False,encoding='utf-8-sig')
 row=b[b['报告日'].astype(str)=='20251231'].iloc[0]
 for col in ['货币资金','交易性金融资产','应收账款','应收款项融资','存货','短期借款','长期借款','一年内到期的非流动负债','合同负债','负债合计','资产总计','股东权益合计']:
  print(col, row.get(col))
except Exception as e: print('balance err',e)
# latest price parse previously
s=requests.get('https://hq.sinajs.cn/list=sh688271',headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15).text
print('sina',s)
t=requests.get('https://qt.gtimg.cn/q=sh688271',headers={'User-Agent':'Mozilla/5.0'},timeout=15).text
print('tencent',t[:1000])

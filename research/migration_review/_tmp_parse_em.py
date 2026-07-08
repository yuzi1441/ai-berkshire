import json, pprint, pandas as pd
raw=json.load(open('reports/工商银行/_tmp_eastmoney_raw.json',encoding='utf-8'))
for name in ['f10main','profit']:
 data=raw[name]['result']['data']
 print('\n##',name, len(data))
 print(data[0].keys())
 for r in data[:8]:
  print({k:r.get(k) for k in ['REPORT_DATE','REPORT_DATE_NAME','NOTICE_DATE','TOTALOPERATEREVE','PARENTNETPROFIT','EPSJB','BPS','ROEJQ','OPERATE_INCOME','INTEREST_NI','FEE_COMMISSION_NI','NETPROFIT','PARENT_NETPROFIT','BASIC_EPS','DILUTED_EPS','TOTAL_PROFIT','OPERATE_PROFIT'] if k in r})
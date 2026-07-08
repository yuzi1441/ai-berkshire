import requests,json
from urllib.parse import urlencode
code='002463'; market='SZ'
params={'type':'RPT_DMSK_FN_INCOME','sty':'ALL','filter':f'(SECUCODE="{code}.{market}")(REPORT_DATE="2025-12-31")','p':'1','ps':'5','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
for typ in ['RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_CASHFLOW','RPT_DMSK_FN_INCOME']:
 params['type']=typ
 url='https://datacenter.eastmoney.com/securities/api/data/get?'+urlencode(params)
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'},timeout=20)
 print('---',typ,r.status_code)
 data=r.json().get('result',{}).get('data',[])
 print('n',len(data))
 if data:
  row=data[0]
  for k,v in row.items():
   if any(s in k for s in ['MONETARY','TOTAL_LIAB','TOTAL_ASSET','NETCASH','CONSTRUCT','FIXED','OPERATE','TOTAL_OPERATE','PARENT','NETPROFIT','BUY']):
    print(k,v)
  print('keys', list(row.keys())[:50])

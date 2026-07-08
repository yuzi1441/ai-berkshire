import requests,json
from urllib.parse import urlencode
code='002463'; market='SZ'
for typ in ['RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_CASHFLOW','RPT_DMSK_FN_INCOME','RPT_F10_FINANCE_GINCOMEQC','RPT_F10_FINANCE_GCASHFLOWQC','RPT_F10_FINANCE_GBALANCEQC']:
 params={'type':typ,'sty':'ALL','filter':f'(SECUCODE="{code}.{market}")','p':'1','ps':'3','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
 url='https://datacenter.eastmoney.com/securities/api/data/get?'+urlencode(params)
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'},timeout=20)
 print('---',typ,r.status_code,r.text[:200])
 try:
  res=r.json().get('result') or {}
  data=res.get('data',[])
 except Exception as e:
  print('json err',e); continue
 print('n',len(data))
 if data:
  row=data[0]
  for k,v in row.items():
   if any(s in k.upper() for s in ['MONETARY','MONEY','TOTAL_LIAB','TOTAL_ASSET','NETCASH','CONSTRUCT','FIXED','OPERATE','PARENT','NETPROFIT','CASH','CAPITAL','PURCHASE']):
    print(k,v)
  print('keys', list(row.keys())[:30])

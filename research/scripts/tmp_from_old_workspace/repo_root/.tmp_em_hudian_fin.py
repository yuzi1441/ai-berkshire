import requests, json, sys
from urllib.parse import urlencode

def get(report_type='年报', ps=10):
 code='002463'; market='SZ'
 params={
  'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL',
  'filter':f'(SECUCODE="{code}.{market}")(REPORT_TYPE="{report_type}")',
  'p':'1','ps':str(ps),'sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'
 }
 url='https://datacenter.eastmoney.com/securities/api/data/get?'+urlencode(params)
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'},timeout=20)
 print('status',r.status_code,r.text[:100])
 data=r.json().get('result',{}).get('data',[])
 print('n',len(data))
 for row in data:
  print(row.get('REPORT_DATE')[:10], row.get('REPORT_DATE_NAME'), row.get('TOTALOPERATEREVE'), row.get('PARENTNETPROFIT'), row.get('EPSJB'), row.get('BPS'), row.get('ROEJQ'), row.get('XSMLL'), row.get('XSJLL'), row.get('MGJYXJJE'))
get('年报')
print('--- q1/all ---')
get('一季报')

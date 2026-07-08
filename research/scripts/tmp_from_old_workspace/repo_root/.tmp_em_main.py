from urllib.parse import urlencode
from urllib.request import Request, urlopen
import json, csv
params={
 'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="002028.SZ")(REPORT_TYPE="年报")','p':'1','ps':'5','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}
url='https://datacenter.eastmoney.com/securities/api/data/get?'+urlencode(params)
print(url)
req=Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'} )
with urlopen(req, timeout=30) as r:
 data=json.loads(r.read().decode('utf-8'))
rows=data.get('result',{}).get('data',[])
print('rows',len(rows))
print(json.dumps(rows[:3],ensure_ascii=False,indent=2)[:5000])
with open('sources/思源电气/eastmoney_mainfinadata_002028.json','w',encoding='utf-8') as f: json.dump(rows,f,ensure_ascii=False,indent=2)
for row in rows[:3]:
 print(row.get('REPORT_DATE_NAME'), row.get('TOTALOPERATEREVE'), row.get('PARENTNETPROFIT'), row.get('BPS'), row.get('EPSJB'), row.get('ROEJQ'), row.get('ZCFZL'), row.get('MGJYXJJE'), row.get('TOTAL_SHARE'))

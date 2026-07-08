import requests, json
urls=[
'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.601088&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&beg=20210101&end=20260706',
'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=116.01088&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58&klt=101&fqt=1&beg=20210101&end=20260706'
]
for url in urls:
 print('URL',url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
  print(r.status_code, r.text[:300])
  data=r.json().get('data') or {}
  kl=data.get('klines') or []
  print('name',data.get('name'),'count',len(kl),'first',kl[:1],'last',kl[-1:])
 except Exception as e: print(type(e),e)

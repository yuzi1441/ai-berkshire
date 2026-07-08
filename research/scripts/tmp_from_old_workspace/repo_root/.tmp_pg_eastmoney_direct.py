import requests, json, re
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'1.600312','fields':'f43,f57,f58,f169,f170,f46,f44,f45,f60,f162,f167,f116,f117,f173,f187,f188,f189,f190,f84,f85,f111,f115,f9,f23,f20,f21,f10,f12,f13,f14,f152'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sh600312.html'},timeout=15)
print(r.status_code,r.text[:1000])
try: print(json.dumps(r.json(),ensure_ascii=False,indent=2)[:2000])
except Exception as e: print(e)

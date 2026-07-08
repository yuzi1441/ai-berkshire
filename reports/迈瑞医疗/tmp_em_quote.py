from pathlib import Path
import requests, json, re
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sz300760.html'}
urls=[
'https://push2.eastmoney.com/api/qt/stock/get?secid=0.300760&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f163,f164,f167,f168,f169,f170,f171,f172,f173,f174,f175,f176,f177,f178,f187,f188,f189',
'https://push2.eastmoney.com/api/qt/stock/get?secid=0.300760&fields=f43,f57,f58,f60,f116,f117,f162,f167,f173,f187,f188'
]
for u in urls:
 r=s.get(u,headers=headers,timeout=20)
 print(r.status_code, r.text[:1000])

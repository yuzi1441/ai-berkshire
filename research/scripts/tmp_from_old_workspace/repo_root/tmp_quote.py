import requests, json, re, datetime
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sh600312.html'}
url='https://push2.eastmoney.com/api/qt/stock/get?secid=1.600312&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f84,f85,f116,f117,f162,f167,f168,f169,f170,f171,f173,f174,f177,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f292'
r=requests.get(url,headers=headers,timeout=20)
print(r.status_code)
print(r.text[:1000])
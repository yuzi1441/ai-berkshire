import requests, json
s=requests.Session(); s.trust_env=False
url='https://push2.eastmoney.com/api/qt/stock/get?secid=1.600372&fields=f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f84,f85,f116,f117,f162,f167,f168,f169,f170,f173,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f288'
r=s.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
print(r.status_code, r.text[:500])
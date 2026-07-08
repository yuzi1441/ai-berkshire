import requests, json
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'0.300760','fields':'f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sz300760.html'},timeout=10)
print(r.url)
print(r.status_code)
print(r.text[:2000])

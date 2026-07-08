import requests
url='https://hq.sinajs.cn/list=sz000400'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'},timeout=20)
print(r.status_code, r.encoding, r.apparent_encoding, r.text[:300])
url2='https://push2.eastmoney.com/api/qt/stock/get?secid=0.000400&fields=f43,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f127,f126,f46,f44,f45,f47,f48,f86'
r2=requests.get(url2,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
print(r2.status_code, r2.text[:500])
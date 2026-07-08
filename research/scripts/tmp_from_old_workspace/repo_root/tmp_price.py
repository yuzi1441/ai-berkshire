import requests,json
url='https://push2.eastmoney.com/api/qt/stock/get?secid=0.002028&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f292'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
print(r.status_code,r.text[:1000])
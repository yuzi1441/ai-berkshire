import requests,json
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'0.002463','fields':'f43,f57,f58,f60,f46,f44,f45,f47,f48,f168,f116,f117,f162,f167,f173,f85,f84,f92,f71,f50,f107'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
print(r.url)
print(r.status_code,r.text[:500])
data=r.json().get('data')
print(json.dumps(data,ensure_ascii=False,indent=2))

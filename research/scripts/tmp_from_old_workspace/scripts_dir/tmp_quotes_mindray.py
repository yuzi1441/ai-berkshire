import requests, re, json, os
os.environ['NO_PROXY']='*'
# Sina
r=requests.get('https://hq.sinajs.cn/list=sz300760',headers={'Referer':'https://finance.sina.com.cn/','User-Agent':'Mozilla/5.0'},timeout=10)
print('SINA', r.status_code, r.text)
# Tencent qt
r=requests.get('https://qt.gtimg.cn/q=sz300760',headers={'User-Agent':'Mozilla/5.0'},timeout=10)
print('TENCENT', r.status_code, r.text[:1000])
# Eastmoney push2
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'0.300760','fields':'f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f84,f85,f168,f169,f170,f171,f162,f167,f50,f51,f52,f86'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=10)
print('EM', r.status_code, r.text[:1000])

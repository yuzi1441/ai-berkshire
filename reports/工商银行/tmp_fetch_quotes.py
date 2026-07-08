import requests, json, re
urls = [
 'https://hq.sinajs.cn/list=sh601398,hk01398',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.601398&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f168,f170,f169,f164,f167,f162,f173,f84,f85,f86,f107,f111,f292',
]
headers={'Referer':'https://finance.sina.com.cn','User-Agent':'Mozilla/5.0'}
for u in urls:
    print('URL',u)
    r=requests.get(u,headers=headers,timeout=10)
    print(r.status_code, r.text[:1000])
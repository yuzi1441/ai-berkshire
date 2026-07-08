import requests, json, re
from urllib.parse import urlencode
headers={'User-Agent':'Mozilla/5.0'}
for url in ['https://qt.gtimg.cn/q=sh600900','https://push2.eastmoney.com/api/qt/stock/get?secid=1.600900&fields=f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f84,f85,f116,f117,f167,f168,f162,f167,f173,f107']:
    r=requests.get(url,headers=headers,timeout=15)
    print('URL',url,'status',r.status_code,'enc',r.encoding)
    r.encoding='gbk' if 'qt.gtimg' in url else 'utf-8'
    print(r.text[:1000])

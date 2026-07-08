import requests, os
for url in [
 'https://hq.sinajs.cn/list=sh600900',
 'https://qt.gtimg.cn/q=sh600900',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600900&fields=f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f46,f44,f45,f60,f84,f85,f9,f23,f115,f127,f128,f129,f130',
]:
    try:
        r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},proxies={'http':None,'https':None})
        print('\nURL',url)
        print(r.status_code, r.headers.get('content-type'), len(r.content))
        print(r.text[:1000])
    except Exception as e:
        print('ERR',url,repr(e))

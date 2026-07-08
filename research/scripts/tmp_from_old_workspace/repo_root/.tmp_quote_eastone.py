import requests, re, json
urls=[
 'https://hq.sinajs.cn/list=sz000682',
 'https://qt.gtimg.cn/q=sz000682',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000682&fields=f43,f57,f58,f169,f170,f46,f44,f45,f60,f116,f117,f85,f84,f162,f167,f168,f50,f48,f49,f51,f52,f173,f115,f114,f113,f112,f111,f110,f262,f263,f264,f267,f268,f255,f256,f257,f258,f59,f152'
]
for u in urls:
    try:
        r=requests.get(u, headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'}, timeout=20, proxies={'http':None,'https':None})
        print('\nURL',u, r.status_code, r.text[:500])
    except Exception as e: print('ERR',u,repr(e))

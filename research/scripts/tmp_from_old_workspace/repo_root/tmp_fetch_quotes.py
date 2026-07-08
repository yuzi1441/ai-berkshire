import requests
urls=[
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000400&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f173,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f152,f59',
 'https://qt.gtimg.cn/q=sz000400',
 'https://hq.sinajs.cn/list=sz000400',
]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.eastmoney.com/'}
for u in urls:
    print('---',u)
    try:
        r=requests.get(u,headers=headers,timeout=15)
        print(r.status_code, r.url)
        print(r.text[:1000])
    except Exception as e:
        print(type(e), e)
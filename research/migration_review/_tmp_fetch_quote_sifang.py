import requests, json, re
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sh601126.html'}
urls=[
'https://push2.eastmoney.com/api/qt/stock/get?secid=1.601126&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f71,f84,f85,f116,f117,f162,f167,f168,f169,f170,f171,f172,f173,f174,f175,f127,f128,f129,f130,f131,f132,f133,f134,f135,f136,f137,f138,f139,f140,f141,f142,f143,f144,f145,f146,f147,f148,f149,f152,f164,f165,f166,f173,f187,f188,f189,f190,f191,f292',
'https://qt.gtimg.cn/q=sh601126',
'https://hq.sinajs.cn/list=sh601126'
]
for u in urls:
    print('\nURL', u[:80])
    try:
        r=requests.get(u,headers=headers,timeout=15)
        print(r.status_code, r.encoding, r.text[:1000])
    except Exception as e:
        print('ERR',repr(e))
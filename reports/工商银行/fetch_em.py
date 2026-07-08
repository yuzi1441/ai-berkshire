import requests, json
urls=['https://push2.eastmoney.com/api/qt/stock/get?secid=1.601398&fields=f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f47,f48,f60,f85,f84,f127,f128,f129,f130,f131,f132,f152','https://push2.eastmoney.com/api/qt/stock/get?secid=116.01398&fields=f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f47,f48,f60,f85,f84,f127,f128,f129,f130,f131,f132,f152']
for u in urls:
    print('---')
    try:
        r=requests.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'},timeout=20)
        print(r.status_code, r.text[:1000])
    except Exception as e: print(repr(e))

import json, urllib.request
urls=[
 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.688235&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f173,f187,f105,f84,f85,f127,f163,f164,f169',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=116.06160&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f173,f187,f105,f84,f85,f127,f163,f164,f169'
]
for url in urls:
    print('\nURL',url)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
        raw=urllib.request.urlopen(req,timeout=20).read().decode('utf-8')
        print(raw[:2000])
    except Exception as e:
        print('ERR',type(e).__name__,e)

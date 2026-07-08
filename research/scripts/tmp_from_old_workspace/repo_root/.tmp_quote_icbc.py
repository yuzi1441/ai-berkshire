import json, urllib.request
urls={
 'em_quote':'https://push2.eastmoney.com/api/qt/stock/get?secid=1.601398&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f174,f115,f128,f152',
 'em_hk':'https://push2.eastmoney.com/api/qt/stock/get?secid=116.01398&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f171,f173,f174,f115,f128,f152',
}
for name,u in urls.items():
    print('---', name)
    try:
        req=urllib.request.Request(u, headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
        print(urllib.request.urlopen(req, timeout=15).read().decode('utf-8')[:2000])
    except Exception as e:
        print('ERR',repr(e))
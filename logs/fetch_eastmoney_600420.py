import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}
urls={
'quote':'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600420&fields=f43,f44,f45,f46,f47,f48,f49,f50,f57,f58,f60,f116,f117,f162,f167,f168,f170,f171,f172,f173,f174,f175,f176,f177,f178,f198,f199,f530',
'kline':'https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.600420&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61&klt=101&fqt=1&beg=20260701&end=20260708',
}
for k,u in urls.items():
    r=requests.get(u,headers=headers,timeout=20)
    print('\n###',k, r.status_code)
    print(json.dumps(r.json(), ensure_ascii=False)[:2000])

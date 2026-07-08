import requests, json
url='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'1.600900','fields':'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f71,f84,f85,f116,f117,f162,f163,f164,f167,f168,f169,f170,f173,f187,f188,f189,f190,f191,f192,f193,f194,f195,f196,f197,f198,f199,f127,f128,f129,f130,f131,f132,f133,f134,f135,f136,f137,f138,f139,f140,f141,f142,f143,f144,f145,f146,f147,f148,f149,f152'}
r=requests.get(url,params=params,timeout=10,headers={'User-Agent':'Mozilla/5.0'})
print(r.url)
print(r.status_code)
print(json.dumps(r.json(),ensure_ascii=False,indent=2)[:5000])

import requests, re, json, pathlib, datetime
outdir=pathlib.Path('data/600420'); outdir.mkdir(parents=True, exist_ok=True)
# Tencent quote
url='https://qt.gtimg.cn/q=sh600420'
r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0'})
print('tencent', r.status_code, r.text[:300])
outdir.joinpath('tencent_quote_20260708.txt').write_text(r.text,encoding='utf-8')
# Eastmoney quote
url2='https://push2.eastmoney.com/api/qt/stock/get'
params={'secid':'1.600420','fields':'f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f84,f85,f116,f117,f162,f167,f168,f169,f170,f171,f172,f173,f174,f175,f176,f177,f178,f292,f107,f111,f113,f114,f115'}
r2=requests.get(url2,params=params,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
print('eastmoney quote', r2.status_code, r2.text[:1000])
outdir.joinpath('eastmoney_quote_20260708.json').write_text(r2.text,encoding='utf-8')

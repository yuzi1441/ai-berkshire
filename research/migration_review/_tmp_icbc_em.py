import requests, json, re, pandas as pd, os, sys
from urllib.parse import urlencode
session=requests.Session()
session.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/'}
urls=[
 ('quote','https://push2.eastmoney.com/api/qt/stock/get', {'secid':'1.601398','fields':'f43,f44,f45,f46,f47,f48,f49,f50,f51,f52,f57,f58,f60,f84,f85,f107,f116,f117,f162,f167,f168,f169,f170,f173,f174,f175,f177,f183,f184,f185,f186,f187,f188,f189,f190,f191,f192,f260,f262,f263,f264,f265,f266,f267,f268,f269,f270,f271,f272,f273,f274,f275,f276,f277,f278,f279,f288,f292'}),
 ('f10main','https://datacenter.eastmoney.com/securities/api/data/get', {'type':'RPT_F10_FINANCE_MAINFINADATA','sty':'ALL','filter':'(SECUCODE="601398.SH")','p':'1','ps':'20','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}),
 ('profit','https://datacenter.eastmoney.com/securities/api/data/get', {'type':'RPT_DMSK_FN_INCOME','sty':'ALL','filter':'(SECUCODE="601398.SH")','p':'1','ps':'20','sr':'-1','st':'REPORT_DATE','source':'HSF10','client':'PC'}),
]
out={}
for name,url,params in urls:
    try:
        r=session.get(url,params=params,headers=headers,timeout=20)
        print(name, r.status_code, r.url[:160], r.text[:120])
        out[name]=r.json()
    except Exception as e:
        print('ERR',name,type(e).__name__,e)
open('reports/工商银行/_tmp_eastmoney_raw.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2)[:2000000])
print('saved')
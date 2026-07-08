import requests, json, re
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sh601126.html'}
urls=[
('em_quote','https://push2.eastmoney.com/api/qt/stock/get?secid=1.601126&fields=f43,f44,f45,f46,f47,f48,f50,f51,f52,f57,f58,f60,f84,f85,f116,f117,f162,f163,f164,f167,f168,f169,f170,f173,f174,f175,f198,f199,f292'),
('em_k','https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=1.601126&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58,f59,f60,f61,f116&klt=101&fqt=0&beg=20260101&end=20260707'),
('sina','https://hq.sinajs.cn/list=sh601126'),
('tencent','https://qt.gtimg.cn/q=sh601126'),
]
for name,url in urls:
    try:
        r=s.get(url,headers=headers,timeout=20)
        print('\n---',name,r.status_code, r.url)
        print(r.text[:2000])
    except Exception as e: print('\nERR',name,type(e).__name__,e)

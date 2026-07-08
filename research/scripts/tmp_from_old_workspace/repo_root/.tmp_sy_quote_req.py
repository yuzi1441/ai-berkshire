import requests, os, json, re
urls=[
 ('tencent','https://qt.gtimg.cn/q=sz002028'),
 ('sina','https://hq.sinajs.cn/list=sz002028'),
 ('eastmoney_quote','https://push2.eastmoney.com/api/qt/stock/get?secid=0.002028&fields=f43,f57,f58,f60,f116,f117,f162,f167,f168,f169,f170,f46,f44,f45,f52,f84,f85,f9,f23,f20,f21,f115'),
]
for name,url in urls:
    print('\n---',name,'---')
    for trust in [True,False]:
        try:
            s=requests.Session(); s.trust_env=trust
            r=s.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
            print('trust',trust,'status',r.status_code,'ct',r.headers.get('content-type'),'len',len(r.content))
            print(r.text[:1000])
            open(f'data/sy_{name}_trust{trust}.txt','w',encoding='utf-8',errors='ignore').write(r.text)
        except Exception as e: print('trust',trust,'ERR',type(e).__name__,e)

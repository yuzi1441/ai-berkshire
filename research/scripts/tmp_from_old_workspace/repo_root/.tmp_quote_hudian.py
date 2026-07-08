import requests, re, json
for name,url,headers in [
 ('sina','https://hq.sinajs.cn/list=sz002463',{'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}),
 ('tencent','https://qt.gtimg.cn/q=sz002463',{'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}),
 ('eastmoney','https://push2.eastmoney.com/api/qt/stock/get?secid=0.002463&fields=f43,f57,f58,f60,f116,f117,f162,f167,f84,f85,f173,f170,f46,f44,f45,f47,f48,f50,f51,f52,f86,f107,f111,f20,f21,f23,f115',{'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
]:
    s=requests.Session(); s.trust_env=False
    try:
        r=s.get(url,headers=headers,timeout=15)
        print('\n---',name,r.status_code,r.headers.get('content-type'))
        print(r.text[:1000])
    except Exception as e:
        print('ERR',name,type(e).__name__,e)

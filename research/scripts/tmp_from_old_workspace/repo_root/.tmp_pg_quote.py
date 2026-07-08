import requests
for url in [
 'https://hq.sinajs.cn/list=sh600312',
 'https://qt.gtimg.cn/q=sh600312',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=1.600312&fields=f43,f57,f58,f116,f117,f162,f167,f168,f85,f84,f2,f3,f9,f23,f20,f21',
]:
    for headers in [{'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'}, {'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'}]:
        s=requests.Session(); s.trust_env=False
        try:
            r=s.get(url,headers=headers,timeout=15)
            print('\nURL',url[:60], r.status_code, r.headers.get('content-type'), r.text[:500])
            break
        except Exception as e:
            print('ERR', url[:40], type(e).__name__, e)

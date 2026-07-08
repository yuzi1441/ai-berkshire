import requests, re, json
s=requests.Session(); s.trust_env=False
urls=['https://qt.gtimg.cn/q=sh600276','http://qt.gtimg.cn/q=sh600276','https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sh600276,day,2026-07-01,2026-07-06,10,qfq']
for url in urls:
 try:
  r=s.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/sh600276/gp'})
  print('\nURL',url,'status',r.status_code,'ct',r.headers.get('content-type'))
  print(r.text[:1500])
 except Exception as e: print('ERR',url,type(e).__name__,e)

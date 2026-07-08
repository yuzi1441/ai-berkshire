import requests, re
for url in ['https://qt.gtimg.cn/q=sh600312','http://qt.gtimg.cn/q=sh600312','https://hq.sinajs.cn/list=sh600312','http://hq.sinajs.cn/list=sh600312']:
 print('\nURL',url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'},timeout=15)
  print(r.status_code,r.encoding,r.text[:500])
 except Exception as e: print('ERR',repr(e))

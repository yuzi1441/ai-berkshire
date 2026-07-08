import requests
for url in ['https://qt.gtimg.cn/q=hk01088','https://hq.sinajs.cn/list=rt_hk01088']:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'},timeout=15)
 print('\nURL',url,r.status_code)
 for enc in ['gbk','utf-8']:
  print(enc, r.content[:500].decode(enc,'replace'))
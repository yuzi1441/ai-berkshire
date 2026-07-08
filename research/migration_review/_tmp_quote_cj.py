import requests, re
urls={
 'sina':'https://hq.sinajs.cn/list=sh600900,sh600905,sh600025,sh600886',
 'tencent':'https://qt.gtimg.cn/q=sh600900,sh600905,sh600025,sh600886',
 'netease':'https://api.money.126.net/data/feed/0600900,0600905,0600025,0600886,money.api'
}
for name,url in urls.items():
 print('\n',name,url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
  print(r.status_code, r.text[:1200])
 except Exception as e: print('ERR',repr(e))

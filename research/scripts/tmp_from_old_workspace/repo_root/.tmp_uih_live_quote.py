import requests, re, json
urls=[
('sina','https://hq.sinajs.cn/list=sh688271'),
('tencent','https://qt.gtimg.cn/q=sh688271'),
('netease','https://api.money.126.net/data/feed/1688271,money.api?callback=cb')]
for name,url in urls:
 print('\n---',name,url)
 try:
  r=requests.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
  print(r.status_code, r.headers.get('content-type'), r.apparent_encoding, len(r.content))
  print(r.content[:500].decode(r.apparent_encoding or 'utf-8', errors='replace'))
 except Exception as e: print('ERR',repr(e))

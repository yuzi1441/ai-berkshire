import requests, pathlib, json, re
out=pathlib.Path('data/huaming_002270')
urls={
 'sina':'https://hq.sinajs.cn/list=sz002270',
 'netease':'https://api.money.126.net/data/feed/1002270,money.api?callback=_ntes_quote_callback'
}
for name,url in urls.items():
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
  print(name,r.status_code,r.encoding,r.text[:1000])
  (out/f'quote_{name}.txt').write_text(r.text,encoding='utf-8',errors='ignore')
 except Exception as e: print(name,'ERR',e)

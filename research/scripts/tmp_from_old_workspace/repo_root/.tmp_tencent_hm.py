import requests
for q in ['sz002270','s_sz002270']:
 url=f'https://qt.gtimg.cn/q={q}'
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
  print(q,r.status_code,r.encoding,r.text[:1000])
 except Exception as e: print(q,'ERR',repr(e))
import requests, pathlib
ids=[('2025annual','2026-04-24','1225161855'),('2026q1','2026-04-29','1225233627'),('2024annual','2025-04-23','1223215550')]
out=pathlib.Path('sources/oriental_electronics'); out.mkdir(parents=True,exist_ok=True)
for name,date,aid in ids:
 url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
 print(name,url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
  print(r.status_code,r.headers.get('content-type'),len(r.content),r.content[:5])
  if r.status_code==200 and r.content[:4]==b'%PDF':
   p=out/f'{name}_{aid}.pdf'; p.write_bytes(r.content); print('saved',p)
 except Exception as e: print(type(e),e)

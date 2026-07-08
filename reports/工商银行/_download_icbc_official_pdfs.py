import urllib.request, pathlib, json, re
urls={
'ICBC_2024_AnnualReport_EN.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2025/Announcement20250425_1.pdf',
'ICBC_2023_AnnualReport_EN.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2024/Announcement20240426_2.pdf',
'ICBC_2022_AnnualReport_EN.pdf':'https://v.icbc.com.cn/userfiles/Resources/ICBCLTD/download/2023/2022AnnualReport20230426.pdf',
'ICBC_2026_Q1_EN_official.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announcement20260429_3.pdf',
'ICBC_2025_AnnualResults_EN.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2026032724.pdf',
}
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
for name,url in urls.items():
 f=out/name
 if f.exists() and f.stat().st_size>10000:
  print(name,'exists',f.stat().st_size); continue
 req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.icbc-ltd.com/'})
 try:
  with urllib.request.urlopen(req,timeout=60) as r:
   data=r.read()
   ct=r.headers.get('content-type')
  print(name,len(data),ct)
  f.write_bytes(data)
 except Exception as e: print(name,'ERR',e)

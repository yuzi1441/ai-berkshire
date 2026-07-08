import requests, pathlib
urls={
 'icbc_2026_q1_en.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announcement20260429_3.pdf',
 'icbc_2025_annual_en.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReport.pdf',
 'icbc_2025_results_en.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2026032724.pdf',
}
headers={'User-Agent':'Mozilla/5.0'}
for fn,u in urls.items():
 p=pathlib.Path(fn)
 if not p.exists() or p.stat().st_size<1000:
  r=requests.get(u,headers=headers,timeout=60)
  print(fn,u,r.status_code,len(r.content),r.headers.get('content-type'))
  p.write_bytes(r.content)
 else:
  print('exists',fn,p.stat().st_size)
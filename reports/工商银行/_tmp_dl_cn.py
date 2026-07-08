import requests, pathlib
urls={
 'icbc_2026_q1_cn_A.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announce20260429_5.pdf',
 'icbc_2026_q1_cn_H.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announce20260429_6.pdf',
 'icbc_2025_annual_cn_A.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReportA.pdf',
 'icbc_2025_annual_cn_H.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReportH.pdf',
}
for fn,u in urls.items():
 p=pathlib.Path(fn)
 if not p.exists() or p.stat().st_size<10000:
  r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=80)
  print(fn,r.status_code,len(r.content),r.headers.get('content-type'),r.content[:4])
  p.write_bytes(r.content)
 else:
  print('exists',fn,p.stat().st_size)
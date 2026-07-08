import requests, pathlib
urls={
 'icbc_2026_q1_cn_try5.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announce20260429_5.pdf',
 'icbc_2025_annual_cn.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReportCN.pdf',
}
for fn,u in urls.items():
 r=requests.get(u,headers={'User-Agent':'Mozilla/5.0'},timeout=60)
 print(fn,u,r.status_code,len(r.content),r.headers.get('content-type'),r.content[:4])
 pathlib.Path(fn).write_bytes(r.content)
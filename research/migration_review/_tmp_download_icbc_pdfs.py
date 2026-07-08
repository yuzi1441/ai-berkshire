import requests, os
s=requests.Session(); s.trust_env=False
urls={
 'ICBC_2025_Annual_A.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReportA.pdf',
 'ICBC_2026_Q1_A.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/Announce20260429_5.pdf',
 'ICBC_2025_Annual_H.pdf':'https://v.icbc.com.cn/userfiles/resources/icbcltd/download/2026/2025AnnualReportH.pdf',
}
outdir='reports/工商银行/sources'
os.makedirs(outdir,exist_ok=True)
for name,url in urls.items():
 path=os.path.join(outdir,name)
 r=s.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=60)
 print(name,r.status_code,r.headers.get('content-type'),len(r.content),r.url)
 open(path,'wb').write(r.content)
 print(path, os.path.getsize(path), r.content[:5])
from pathlib import Path
import requests, pdfplumber, re, json, sys
repo=Path.cwd()
out=repo/'sources'/'sifang'
out.mkdir(parents=True, exist_ok=True)
urls={
 '2025_annual_sse.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-24/601126_20260324_2K9N.pdf',
 '2026_q1_sse.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf',
 'hkex_prospectus_2026.pdf':'https://www1.hkexnews.hk/app/sehk/2026/108647/documents/sehk26061600483_c.pdf',
}
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for fn,url in urls.items():
 p=out/fn
 if not p.exists() or p.stat().st_size<1000:
  r=s.get(url,headers=headers,timeout=60)
  print(fn, r.status_code, r.headers.get('content-type'), len(r.content))
  r.raise_for_status(); p.write_bytes(r.content)
 else: print(fn,'exists',p.stat().st_size)
 # extract text limited all pages if manageable
 try:
  txtp=p.with_suffix('.txt')
  if not txtp.exists() or txtp.stat().st_size<1000:
   texts=[]
   with pdfplumber.open(p) as pdf:
    print(fn,'pages',len(pdf.pages))
    for i,page in enumerate(pdf.pages):
     t=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
     texts.append(f'\n\n---PAGE {i+1}---\n'+t)
   txtp.write_text('\n'.join(texts),encoding='utf-8')
 except Exception as e: print('extract err',fn,e)
print('done', out)

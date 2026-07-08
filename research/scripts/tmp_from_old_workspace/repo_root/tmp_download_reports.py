import requests, os, re
base='http://static.cninfo.com.cn/'
files={
 '2025_annual.pdf':'finalpage/2026-02-27/1224986242.PDF',
 '2026_q1.pdf':'finalpage/2026-04-27/1225181771.PDF',
 '2024_annual.pdf':'finalpage/2025-04-11/1223055875.PDF',
}
outdir='reports/华明装备/source_docs'
os.makedirs(outdir, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
 url=base+path
 fn=os.path.join(outdir,name)
 if os.path.exists(fn) and os.path.getsize(fn)>10000:
  print('exists',fn,os.path.getsize(fn)); continue
 r=requests.get(url,headers=headers,timeout=30)
 print(url,r.status_code,r.headers.get('content-type'),len(r.content))
 open(fn,'wb').write(r.content)
 print('saved',fn,os.path.getsize(fn),r.content[:8])

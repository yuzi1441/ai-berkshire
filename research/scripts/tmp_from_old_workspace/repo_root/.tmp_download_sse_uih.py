import requests, pathlib, hashlib
base=pathlib.Path('sources/联影医疗')
urls={
 '2025年报_sse.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_NTY7.pdf',
 '2026Q1_sse.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_78JE.pdf'
}
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for name,url in urls.items():
 r=s.get(url,headers=headers,timeout=60)
 print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4], hashlib.sha256(r.content).hexdigest()[:16])
 if r.content[:4]==b'%PDF': (base/name).write_bytes(r.content)

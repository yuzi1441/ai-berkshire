import requests, pathlib
base='https://www.sse.com.cn'
urls={
 'sse_601398_2026_q1.pdf': base+'/disclosure/listedinfo/announcement/c/new/2026-04-30/601398_20260430_VX32.pdf',
 'sse_601398_2025_annual.pdf': base+'/disclosure/listedinfo/announcement/c/new/2026-03-28/601398_20260328_JYCS.pdf'
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for fn,u in urls.items():
 r=requests.get(u,headers=headers,timeout=60)
 print(fn,r.status_code,len(r.content),r.headers.get('content-type'),r.content[:4])
 pathlib.Path(fn).write_bytes(r.content)
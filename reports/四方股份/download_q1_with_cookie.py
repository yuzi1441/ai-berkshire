import requests, pathlib
url='https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/','Cookie':'acw_sc__v2=6a4be185bca47ac4f7d5355abb3d67b45e6da775'}
r=requests.get(url,headers=headers,timeout=60)
print(r.status_code, r.headers.get('content-type'), len(r.content), r.content[:8])
path=pathlib.Path('sifang_2026q1_sse_real.pdf')
path.write_bytes(r.content)
print(path.resolve(), path.stat().st_size)

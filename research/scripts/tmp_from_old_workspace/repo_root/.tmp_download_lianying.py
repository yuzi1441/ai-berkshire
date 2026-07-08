import requests, pathlib
ids={'annual':'1225233728','q1':'1225233744'}
out=pathlib.Path('sources/联影医疗'); out.mkdir(parents=True, exist_ok=True)
for k,id in ids.items():
    url=f'http://static.cninfo.com.cn/finalpage/2026-04-29/{id}.PDF'
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
    print(k, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
    p=out/f'lianying_{k}_20260429_{id}.pdf'
    p.write_bytes(r.content)
    print(p)

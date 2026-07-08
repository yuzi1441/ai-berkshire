import pathlib, requests
base=pathlib.Path.cwd()
urls={
 'sifang_2026q1_sse.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf',
 'sifang_2025_ar_cninfo.pdf':'http://static.cninfo.com.cn/finalpage/2026-03-24/1225025430.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
for name,url in urls.items():
    p=base/name
    if p.exists() and p.stat().st_size>10000:
        print('exists', name, p.stat().st_size)
        continue
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:8])
    r.raise_for_status()
    p.write_bytes(r.content)
    print('wrote', p.resolve(), p.stat().st_size)

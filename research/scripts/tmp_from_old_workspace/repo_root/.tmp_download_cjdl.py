import requests, pathlib
urls = {
 'annual2025':'https://www.ctg.com.cn/cypc/attachDir/2026/05/2026051815345898336.pdf',
 'q1_2026':'https://www.cypc.com.cn/cypc/attachDir/2026/05/2026051815335596092.pdf',
}
out=pathlib.Path('sources/长江电力'); out.mkdir(parents=True, exist_ok=True)
for name,url in urls.items():
    p=out/f'{name}.pdf'
    r=requests.get(url,timeout=30,headers={'User-Agent':'Mozilla/5.0'})
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    r.raise_for_status()
    p.write_bytes(r.content)
    print(p.resolve())

import requests, pathlib
urls={
 'annual2025':'https://www.cypc.com.cn/cypc/attachDir/2026/05/2026051815345898336.pdf',
 'q1_2026':'https://www.cypc.com.cn/cypc/attachDir/2026/05/2026051815335596092.pdf',
 'annual2024':'https://www.cypc.com.cn/cypc/attachDir/2025/05/2025050612554995408.pdf',
}
out=pathlib.Path('data/长江电力')
out.mkdir(parents=True, exist_ok=True)
for k,u in urls.items():
    p=out/f'{k}.pdf'
    if not p.exists() or p.stat().st_size<10000:
        r=requests.get(u, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
        print(k, r.status_code, r.headers.get('content-type'), len(r.content))
        r.raise_for_status(); p.write_bytes(r.content)
    else:
        print(k, 'exists', p.stat().st_size)

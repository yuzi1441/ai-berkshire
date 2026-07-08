import requests, pathlib
urls = {
  'xj_2025_annual.pdf': 'https://static.cninfo.com.cn/finalpage/2026-04-11/1225096177.PDF',
  'xj_2026_q1.pdf': 'https://static.cninfo.com.cn/finalpage/2026-04-11/1225096189.PDF',
}
out = pathlib.Path('source_docs/xj-electric')
for name, url in urls.items():
    p=out/name
    r=requests.get(url, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    r.raise_for_status()
    p.write_bytes(r.content)
    print(p, p.stat().st_size)

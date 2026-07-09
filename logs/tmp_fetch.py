import requests, pathlib
url='https://static.cninfo.com.cn/finalpage/2026-03-27/1225037769.PDF'
out=pathlib.Path('research/source_docs/国药现代/国药现代-2025年度报告-cninfo-1225037769.PDF')
out.parent.mkdir(parents=True, exist_ok=True)
r=requests.get(url, timeout=30, headers={'User-Agent':'Mozilla/5.0'})
print(r.status_code, r.headers.get('content-type'), len(r.content), r.content[:20])
out.write_bytes(r.content)
print(out.resolve())

import requests, re, pathlib, json
from urllib.parse import urlparse
base=pathlib.Path('research/source_docs/中航机载'); base.mkdir(parents=True, exist_ok=True)
urls={
 'annual_2025_sina.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-3/2026-03-28/12027374.PDF',
}
for name,url in urls.items():
    p=base/name
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    p.write_bytes(r.content)
print('done', base.resolve())
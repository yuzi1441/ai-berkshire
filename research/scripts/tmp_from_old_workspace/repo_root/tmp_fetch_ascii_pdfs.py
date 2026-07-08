import requests, pathlib
out=pathlib.Path('reports')/'四方股份'/'sources'
urls={
 '601126_2026Q1.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-30/12277344.PDF',
 '601126_2025AR.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-3/2026-03-24/12011598.PDF',
 '601126_2025Q1.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2025/2025-4/2025-04-29/11732793.PDF',
}
# if id not correct for 2025Q1, query from html? We'll still attempt.
for fname,url in urls.items():
    p=out/fname
    if p.exists() and p.stat().st_size>10000:
        print('exists', p, p.stat().st_size); continue
    r=requests.get(url,timeout=90,headers={'User-Agent':'Mozilla/5.0'})
    print(fname, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:5])
    p.write_bytes(r.content)
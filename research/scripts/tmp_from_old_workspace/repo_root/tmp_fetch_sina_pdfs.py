import requests, pathlib
out=pathlib.Path('reports')/'四方股份'/'sources'
out.mkdir(parents=True, exist_ok=True)
urls={
 '601126_四方股份2026年第一季度报告_sina.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-30/12277344.PDF',
 '601126_四方股份2025年年度报告_sina.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-3/2026-03-24/12011598.PDF',
}
for fname,url in urls.items():
    r=requests.get(url,timeout=90,headers={'User-Agent':'Mozilla/5.0'})
    print(fname, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:5])
    p=out/fname
    p.write_bytes(r.content)
    print(p.resolve(), p.stat().st_size)
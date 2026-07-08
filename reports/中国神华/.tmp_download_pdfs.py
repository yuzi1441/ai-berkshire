import urllib.request, pathlib
base=pathlib.Path.cwd()/"sources"
base.mkdir(exist_ok=True)
urls={
 'annual2025.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-3/2026-03-31/12048559.PDF',
 'q1_2026.pdf':'http://file.finance.sina.com.cn/211.154.219.97:9494/MRGG/CNSESH_STOCK/2026/2026-4/2026-04-25/12188063.PDF'
}
for name,url in urls.items():
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    data=urllib.request.urlopen(req, timeout=60).read()
    p=base/name
    p.write_bytes(data)
    print(p, len(data), data[:5])

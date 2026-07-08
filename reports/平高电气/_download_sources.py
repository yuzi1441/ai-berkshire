from pathlib import Path
import urllib.request
urls = {
    'annual_2025.pdf': 'https://static.cninfo.com.cn/finalpage/2026-04-11/1225093676.PDF',
    'q1_2026.pdf': 'https://stockmc.xueqiu.com/202604/600312_20260422_QF5E.pdf',
    'order_2025_773m.pdf': 'https://big5.sse.com.cn/site/cht/www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2025-11-29/600312_20251129_OXU0.pdf',
}
out = Path.cwd() / '_sources'
out.mkdir(exist_ok=True)
for name, url in urls.items():
    path = out / name
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    with urllib.request.urlopen(req, timeout=30) as r:
        path.write_bytes(r.read())
    print(path, path.stat().st_size)
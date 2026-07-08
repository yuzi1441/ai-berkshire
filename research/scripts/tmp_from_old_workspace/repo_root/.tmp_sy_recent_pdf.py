import requests, os
items=[('2025_dividend','2026-07-01','1225399910'),('board_change','2026-06-27','1225393424'),('capex_transformer','2026-06-17','1225373731'),('capex_rugao','2026-06-04','1225349917'),('buyback_result','2026-06-16','1225371122'),('exec_reduce','2026-06-25','1225385724'),('exec_reduce2','2026-05-15','1225306674')]
os.makedirs('sources/002028/recent',exist_ok=True)
for name,date,aid in items:
    url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    r=requests.get(url,timeout=20)
    print(name, r.status_code, len(r.content), r.headers.get('content-type'), r.content[:10])
    open(f'sources/002028/recent/{name}_{aid}.pdf','wb').write(r.content)

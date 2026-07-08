import requests, os
items=[('2026Q1','2026-04-25','1225177123'),('2024AR','2025-04-19','1223145398'),('2023AR','2024-04-20','1219702367')]
os.makedirs('sources/002028', exist_ok=True)
for name,date,aid in items:
    url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    r=requests.get(url,timeout=30)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:20])
    open(f'sources/002028/{name}_{aid}.pdf','wb').write(r.content)

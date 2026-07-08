import requests
ids=['1225032585','1222961962','1219650115','1216518776','1213053755','1225145521']
for aid in ids:
    y={'1225032585':'2026-03-26','1222961962':'2025-03-31','1219650115':'2024-04-18','1216518776':'2023-04-22','1213053755':'2022-04-23','1225145521':'2026-04-23'}[aid]
    url=f'http://static.cninfo.com.cn/finalpage/{y}/{aid}.PDF'
    try:
        r=requests.head(url,timeout=10,allow_redirects=True)
        print(aid,r.status_code,r.headers.get('content-type'),r.headers.get('content-length'),url)
    except Exception as e: print(aid,e)

import requests, pathlib
ids={
'2025AR':('2026-03-26','1225032585'),
'2024AR':('2025-03-31','1222961962'),
'2023AR':('2024-04-18','1219650115'),
'2022AR':('2023-04-22','1216518776'),
'2021AR':('2022-04-23','1213053755'),
'2026Q1':('2026-04-23','1225145521'),
}
out=pathlib.Path('sources/hengrui'); out.mkdir(parents=True,exist_ok=True)
for name,(date,aid) in ids.items():
    url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    path=out/f'{name}_{aid}.pdf'
    if not path.exists() or path.stat().st_size<1000:
        r=requests.get(url,timeout=30)
        print(name,r.status_code,r.headers.get('content-type'),len(r.content))
        path.write_bytes(r.content)
    else: print(name,'exists',path.stat().st_size)

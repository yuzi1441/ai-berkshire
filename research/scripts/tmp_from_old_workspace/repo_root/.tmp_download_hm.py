import requests, os
ids=['1224986242','1225181771','1223055875','1219567826','1216380949','1213571762']
os.makedirs('sources/002270', exist_ok=True)
for aid in ids:
    url=f'http://static.cninfo.com.cn/finalpage/2026-02-27/{aid}.PDF'
    # need date per id maybe from list map
print('test')
for date,aid,name in [('2026-02-27','1224986242','2025AR'),('2026-04-27','1225181771','2026Q1'),('2025-04-11','1223055875','2024AR'),('2024-04-11','1219567826','2023AR'),('2023-04-12','1216380949','2022AR'),('2022-06-01','1213571762','2021AR_revised')]:
    url=f'http://static.cninfo.com.cn/finalpage/{date}/{aid}.PDF'
    r=requests.get(url, timeout=20, headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
    if r.status_code==200 and r.content[:4]==b'%PDF':
        open(f'sources/002270/{name}_{aid}.pdf','wb').write(r.content)

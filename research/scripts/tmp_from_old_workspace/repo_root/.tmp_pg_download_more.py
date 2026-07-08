import requests, pathlib
base=pathlib.Path('sources/平高电气')
base.mkdir(parents=True, exist_ok=True)
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
files={
 '2024_annual_full.pdf':'https://static.cninfo.com.cn/finalpage/2025-04-11/1223054837.PDF',
 '2023_annual.pdf':'https://static.cninfo.com.cn/finalpage/2024-04-11/1219567393.PDF',
 '2022_annual.pdf':'https://static.cninfo.com.cn/finalpage/2023-04-21/1216496824.PDF',
 '2021_annual.pdf':'https://static.cninfo.com.cn/finalpage/2022-04-15/1212920716.PDF',
}
for name,url in files.items():
    p=base/name
    if p.exists() and p.stat().st_size>1000:
        print('exists', name, p.stat().st_size); continue
    r=s.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
    r.raise_for_status(); p.write_bytes(r.content)

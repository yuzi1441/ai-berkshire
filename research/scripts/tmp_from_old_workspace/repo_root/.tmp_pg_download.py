import requests, pathlib
base=pathlib.Path('sources/平高电气')
base.mkdir(parents=True, exist_ok=True)
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'}
files={
 '2025_annual.pdf':'https://static.cninfo.com.cn/finalpage/2026-04-11/1225093676.PDF',
 '2026_q1.pdf':'https://static.cninfo.com.cn/finalpage/2026-04-22/1225134836.PDF',
 '2024_annual.pdf':'https://static.cninfo.com.cn/finalpage/2025-04-11/1223054856.PDF',
}
for name,url in files.items():
    p=base/name
    r=s.get(url,headers=headers,timeout=30)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
    r.raise_for_status()
    p.write_bytes(r.content)
    print('saved', p.resolve())

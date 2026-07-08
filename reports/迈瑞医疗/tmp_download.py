import requests, pathlib
base='http://static.cninfo.com.cn/'
files={
 'mindray_2025_annual.pdf':'finalpage/2026-03-31/1225059012.PDF',
 'mindray_2026_q1.pdf':'finalpage/2026-04-29/1225229244.PDF',
}
out=pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports'
out.mkdir(parents=True, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
    url=base+path
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content))
    p=out/name
    p.write_bytes(r.content)
    print(p)

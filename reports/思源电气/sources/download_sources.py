import requests, pathlib
base='http://static.cninfo.com.cn/'
files={
 'siyuan_2025_annual.pdf':'finalpage/2026-04-18/1225117829.PDF',
 'siyuan_2026_q1.pdf':'finalpage/2026-04-25/1225177123.PDF',
}
out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\思源电气\sources')
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
    url=base+path
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), url)
    (out/name).write_bytes(r.content)

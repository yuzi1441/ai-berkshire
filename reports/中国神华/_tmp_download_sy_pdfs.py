import requests, pathlib
base='http://static.cninfo.com.cn/'
files={
 '2025_annual.pdf':'finalpage/2026-03-31/1225064293.PDF',
 '2026_q1.pdf':'finalpage/2026-04-25/1225185746.PDF',
 '2025_dividend.pdf':'finalpage/2026-03-31/1225064313.PDF'
}
out=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\sources')
out.mkdir(exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
 u=base+path
 r=requests.get(u,headers=headers,timeout=40)
 print(name,r.status_code,r.headers.get('content-type'),len(r.content),u)
 (out/name).write_bytes(r.content)
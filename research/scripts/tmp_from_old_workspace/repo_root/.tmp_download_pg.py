import requests, pathlib
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
urls={
'annual2025':'http://static.cninfo.com.cn/finalpage/2026-04-11/1225093676.PDF',
'q1_2026':'http://static.cninfo.com.cn/finalpage/2026-04-22/1225134836.PDF',
'rights2025':'http://static.cninfo.com.cn/finalpage/2026-06-18/1225375496.PDF',
}
out=pathlib.Path('sources/pinggao'); out.mkdir(parents=True,exist_ok=True)
for name,url in urls.items():
 r=requests.get(url,headers=headers,timeout=30)
 print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:4])
 p=out/(name+'.pdf')
 p.write_bytes(r.content)
 print(p.resolve())

import requests, pathlib, json
items={
'ICBC_Q1_2026':'finalpage/2026-04-30/1225255391.PDF',
'ICBC_AR_2025':'finalpage/2026-03-28/1225047240.PDF',
}
out=pathlib.Path('source_pdfs'); out.mkdir(exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in items.items():
    url='http://static.cninfo.com.cn/'+path
    r=requests.get(url,headers=headers,timeout=60)
    print(name,r.status_code,len(r.content),r.headers.get('content-type'),r.content[:4])
    (out/(name+'.pdf')).write_bytes(r.content)

import requests, pathlib, sys, re
base='https://www.sse.com.cn'
files={
'ICBC_AR_2024':'/disclosure/listedinfo/announcement/c/new/2025-03-29/601398_20250329_SYXH.pdf',
'ICBC_AR_2023':'/disclosure/listedinfo/announcement/c/new/2024-03-28/601398_20240328_9QIS.pdf',
'ICBC_AR_2022':'/disclosure/listedinfo/announcement/c/new/2023-03-31/601398_20230331_AH3A.pdf',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
for name,path in files.items():
    f=out/(name+'.pdf')
    if f.exists() and f.stat().st_size>10000:
        print(name,'exists',f.stat().st_size)
        continue
    r=requests.get(base+path,headers=headers,timeout=60)
    print(name, r.status_code, len(r.content), r.headers.get('content-type'))
    f.write_bytes(r.content)

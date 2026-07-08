import urllib.request, pathlib, re
headers={'User-Agent':'codex research contact@example.com'}
base='https://www.sec.gov/Archives/edgar/data/1651308/'
files={
'2026Q1_10Q':'000162828026030867/bgne-20260331.htm',
'2025_10K':'000162828026011946/bgne-20251231.htm',
'2026Q1_8K':'000162828026030866/bgne-20260506.htm',
'2025FY_8K':'000162828026011941/bgne-20260226.htm',
}
out=pathlib.Path('sources/sec_beone'); out.mkdir(parents=True,exist_ok=True)
for name,path in files.items():
    url=base+path
    print('fetch',name,url)
    req=urllib.request.Request(url,headers=headers)
    data=urllib.request.urlopen(req,timeout=30).read()
    (out/f'{name}.html').write_bytes(data)
    print(name,len(data))
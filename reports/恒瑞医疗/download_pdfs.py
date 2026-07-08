import urllib.request, pathlib
base='http://static.cninfo.com.cn/'
files={
 'hengrui_2025_annual.pdf':'finalpage/2026-03-26/1225032585.PDF',
 'hengrui_2026_q1.pdf':'finalpage/2026-04-23/1225145521.PDF'
}
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
for name,path in files.items():
    url=base+path
    req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
    data=urllib.request.urlopen(req,timeout=60).read()
    p=out/name; p.write_bytes(data)
    print(name, len(data), data[:5])
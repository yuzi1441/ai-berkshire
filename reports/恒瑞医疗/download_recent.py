import urllib.request, pathlib
files={
 'hengrui_20260703_buyback.pdf':'finalpage/2026-07-03/1225405465.PDF',
 'hengrui_20260623_ema.pdf':'finalpage/2026-06-23/1225380471.PDF',
 'hengrui_20260521_dividend.pdf':'finalpage/2026-05-21/1225320201.PDF'
}
base='http://static.cninfo.com.cn/'
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
for name,path in files.items():
    req=urllib.request.Request(base+path,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'})
    data=urllib.request.urlopen(req,timeout=30).read()
    (out/name).write_bytes(data)
    print(name,len(data),data[:5])
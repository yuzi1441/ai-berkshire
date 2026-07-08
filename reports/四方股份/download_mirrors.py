import requests, pathlib
files={
'sifang_2026q1_xueqiu.pdf':'https://stockmc.xueqiu.com/202604/601126_20260430_8ESA.pdf',
'sifang_2025_ar_dataclouds.pdf':'https://dataclouds.cninfo.com.cn/shgonggao/hsomarket/2026/20260323/7c635303d2fa44f7b2d85435386eeeb1.PDF'
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://xueqiu.com/'}
for name,url in files.items():
    p=pathlib.Path(name)
    if p.exists() and p.stat().st_size>10000:
        print('exists', name, p.stat().st_size)
        continue
    r=requests.get(url,headers=headers,timeout=60)
    print(name, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:8])
    r.raise_for_status()
    p.write_bytes(r.content)
    print('wrote', p.resolve(), p.stat().st_size)

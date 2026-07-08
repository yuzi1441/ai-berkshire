import re, requests, pathlib
posList=[0xf,0x23,0x1d,0x18,0x21,0x10,0x1,0x26,0xa,0x9,0x13,0x1f,0x28,0x1b,0x16,0x17,0x19,0xd,0x6,0xb,0x27,0x12,0x14,0x8,0xe,0x15,0x20,0x1a,0x2,0x1e,0x7,0x4,0x11,0x5,0x3,0x1c,0x22,0x25,0xc,0x24]
mask='3000176000856006061501533003690027800375'
def acw(arg1):
    out=['']*len(posList)
    for i,ch in enumerate(arg1):
        for j,p in enumerate(posList):
            if p==i+1: out[j]=ch
    arg2=''.join(out)
    res=''
    for i in range(0,min(len(arg2),len(mask)),2):
        x=int(arg2[i:i+2],16)^int(mask[i:i+2],16)
        res += f'{x:02x}'
    return res
base='https://www.sse.com.cn'
items={
 '600900_2025_annual.pdf':'/disclosure/listedinfo/announcement/c/new/2026-04-30/600900_20260430_WC8R.pdf',
 '600900_2025_esg.pdf':'/disclosure/listedinfo/announcement/c/new/2026-04-30/600900_20260430_0VWG.pdf',
 '600900_2026_q1_power.pdf':'/disclosure/listedinfo/announcement/c/new/2026-04-10/600900_20260410_0PQB.pdf',
 '600900_2026_h1_power.pdf':'/disclosure/listedinfo/announcement/c/new/2026-07-07/600900_20260707_GHOM.pdf',
 '600900_2026_2030_dividend_plan.pdf':'/disclosure/listedinfo/announcement/c/new/2025-08-15/600900_20250815_NGNF.pdf',
}
outdir=pathlib.Path('sources'); outdir.mkdir(exist_ok=True)
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'})
for name,path in items.items():
    url=base+path
    r=s.get(url,timeout=20)
    content=r.content
    if content[:5].lower()==b'<html':
        text=content.decode('utf-8','ignore')
        m=re.search(r"var arg1='([0-9A-Fa-f]+)'", text)
        if not m:
            print(name, 'no arg1', len(content)); continue
        val=acw(m.group(1))
        s.cookies.set('acw_sc__v2', val, domain='www.sse.com.cn', path='/')
        r=s.get(url,timeout=30)
        content=r.content
    (outdir/name).write_bytes(content)
    print(name, len(content), content[:8])
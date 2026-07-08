from pathlib import Path
import re, base64, requests
html=(Path('sources/sifang/2025_annual_sse.pdf').read_text(encoding='utf-8'))
arg1=re.search(r"arg1='([0-9A-F]+)'", html).group(1)
# decode mask from base64 literal in script: MzAw... = 300017...
mask=base64.b64decode('MzAwMDE3NjAwMDg1NjAwNjA2MTUwMTUzMzAwMzY5MDAyNzgwMDM3NQ==').decode()
pos=[0xf,0x23,0x1d,0x18,0x21,0x10,0x1,0x26,0xa,0x9,0x13,0x1f,0x28,0x1b,0x16,0x17,0x19,0xd,0x6,0xb,0x27,0x12,0x14,0x8,0xe,0x15,0x20,0x1a,0x2,0x1e,0x7,0x4,0x11,0x5,0x3,0x1c,0x22,0x25,0xc,0x24]
out=['']*len(pos)
for i,ch in enumerate(arg1):
 for j,p in enumerate(pos):
  if p==i+1: out[j]=ch
arg2=''.join(out)
arg3=''
for i in range(0,min(len(arg2),len(mask)),2):
 xor=(int(arg2[i:i+2],16)^int(mask[i:i+2],16))
 arg3+=f'{xor:02x}'
print('cookie',arg3)
urls={
 '2025_annual_sse_real.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-24/601126_20260324_2K9N.pdf',
 '2026_q1_sse_real.pdf':'https://www.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf',
}
s=requests.Session(); s.trust_env=False
s.cookies.set('acw_sc__v2',arg3,domain='sse.com.cn',path='/')
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
outdir=Path('sources/sifang')
for fn,url in urls.items():
 r=s.get(url,headers=headers,timeout=60)
 print(fn,r.status_code,r.headers.get('content-type'),len(r.content),r.content[:5])
 (outdir/fn).write_bytes(r.content)

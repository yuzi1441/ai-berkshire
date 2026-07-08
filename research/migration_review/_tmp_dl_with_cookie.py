import requests, pathlib, subprocess, re, json, pdfplumber
root=pathlib.Path('reports/联影医疗/sources')
base='https://www.sse.com.cn'
paths={
 '2026Q1': '/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_78JE.pdf',
 '2025Annual': '/disclosure/listedinfo/announcement/c/new/2026-04-29/688271_20260429_NTY7.pdf',
 '2024Annual': '/disclosure/listedinfo/announcement/c/new/2025-04-29/688271_20250429_BP0A.pdf',
}
s=requests.Session(); headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
# get challenge
r=s.get(base+paths['2026Q1'],headers=headers,timeout=20)
if not r.content.startswith(b'%PDF'):
    html=r.text
    js=re.search(r'<script>(.*)</script>', html, re.S).group(1)
    jsfile=pathlib.Path('_tmp_sse_cookie_eval.js')
    jsfile.write_text("var location={host:'www.sse.com.cn'};\nvar document={cookie:'', location:{reload:function(){}}};\n"+js+"\nconsole.log(document.cookie);\n",encoding='utf-8')
    cookie=subprocess.check_output(['node',str(jsfile)],text=True,encoding='utf-8').strip().split(';')[0]
    k,v=cookie.split('=',1)
    s.cookies.set(k,v,domain='www.sse.com.cn',path='/')
    s.cookies.set(k,v,domain='.sse.com.cn',path='/')
    print('cookie',cookie)
for name,path in paths.items():
    pdf=root/f'{name}.pdf'
    r=s.get(base+path,headers=headers,timeout=60)
    print(name,r.status_code,len(r.content),r.content[:4])
    pdf.write_bytes(r.content)
    if not r.content.startswith(b'%PDF'):
        print(r.text[:200])
        continue
    txt=root/f'{name}.txt'
    parts=[]
    with pdfplumber.open(str(pdf)) as p:
        print('pages',len(p.pages))
        for i,pg in enumerate(p.pages):
            t=pg.extract_text(x_tolerance=1,y_tolerance=3) or ''
            parts.append(f'\n---PAGE {i+1}---\n'+t)
    txt.write_text('\n'.join(parts),encoding='utf-8')
    print(txt, txt.stat().st_size)

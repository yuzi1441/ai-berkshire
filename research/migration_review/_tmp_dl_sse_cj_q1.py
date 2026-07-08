import requests, pathlib, subprocess, re, pdfplumber, time
root=pathlib.Path('reports/长江电力/sources'); root.mkdir(parents=True,exist_ok=True)
base='https://www.sse.com.cn'
paths={
 '2025Annual': '/disclosure/listedinfo/announcement/c/new/2026-04-30/600900_20260430_WC8R.pdf',
 '2026Q1': '/disclosure/listedinfo/announcement/c/new/2026-04-30/600900_20260430_PRUY.pdf',
 '2026H1Power':'/disclosure/listedinfo/announcement/c/new/2026-07-07/600900_20260707_GHOM.pdf',
 '2025Power':'/disclosure/listedinfo/announcement/c/new/2026-01-06/600900_20260106_NTH4.pdf',
 '2025InterimDividend':'/disclosure/listedinfo/announcement/c/new/2026-02-05/600900_20260205_GAQT.pdf',
}
# find q1 if guessed path not exists: query list and match
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
s=requests.Session()
# function fetch with anti-bot cookie
def get_pdf(path):
    r=s.get(base+path,headers=headers,timeout=30)
    if r.content.startswith(b'%PDF'):
        return r
    html=r.text
    m=re.search(r'<script>(.*)</script>', html, re.S)
    if not m:
        return r
    jsfile=pathlib.Path('_tmp_sse_cookie_eval_cj.js')
    jsfile.write_text("var location={host:'www.sse.com.cn'};\nvar document={cookie:'', location:{reload:function(){}}};\n"+m.group(1)+"\nconsole.log(document.cookie);\n",encoding='utf-8')
    cookie=subprocess.check_output(['node',str(jsfile)],text=True,encoding='utf-8').strip().split(';')[0]
    k,v=cookie.split('=',1)
    s.cookies.set(k,v,domain='www.sse.com.cn',path='/')
    s.cookies.set(k,v,domain='.sse.com.cn',path='/')
    print('cookie',cookie)
    return s.get(base+path,headers=headers,timeout=60)
# update q1 via query
import json
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={'jsonCallBack':'jsonpCallback12345','isPagination':'true','productId':'600900','securityType':'0101','reportType2':'','reportType':'ALL','beginDate':'2026-04-01','endDate':'2026-05-10','pageHelp.pageSize':'50','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':str(int(time.time()*1000))}
r=s.get(url,params=params,headers={**headers,'Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'},timeout=20)
mm=re.search(r'jsonpCallback12345\((.*)\)$',r.text)
if mm:
 js=json.loads(mm.group(1)); items=js.get('result') or js.get('pageHelp',{}).get('data') or []
 for item in items:
  title=item.get('TITLE') or ''
  if '第一季度报告' in title:
   paths['2026Q1']=item['URL']; print('found Q1', title, item['URL'])
for name,path in paths.items():
    pdf=root/f'sse_{name}.pdf'
    rr=get_pdf(path)
    print(name,rr.status_code,len(rr.content),rr.content[:5])
    pdf.write_bytes(rr.content)
    if not rr.content.startswith(b'%PDF'):
        (root/f'sse_{name}.html').write_text(rr.text[:20000],encoding='utf-8')
        continue
    parts=[]
    with pdfplumber.open(str(pdf)) as p:
        print(name,'pages',len(p.pages))
        for i,pg in enumerate(p.pages):
            t=pg.extract_text(x_tolerance=1,y_tolerance=3) or ''
            parts.append(f'\n---PAGE {i+1}---\n'+t)
    txt=root/f'sse_{name}.txt'
    txt.write_text('\n'.join(parts),encoding='utf-8')
    print('txt',txt,txt.stat().st_size)


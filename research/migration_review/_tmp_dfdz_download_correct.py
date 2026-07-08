import requests, pathlib, pdfplumber
src=pathlib.Path.cwd()/'source_docs'
src.mkdir(exist_ok=True)
files={
 'annual2025':'finalpage/2026-04-24/1225161855.PDF',
 'audit2025':'finalpage/2026-04-24/1225161857.PDF',
 'q1_2026':'finalpage/2026-04-29/1225233627.PDF',
 'dividend2025':'finalpage/2026-07-01/1225399607.PDF',
 'profit_dist':'finalpage/2026-04-24/1225161863.PDF',
 'esg2025':'finalpage/2026-04-24/1225161872.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
    url='http://static.cninfo.com.cn/'+path
    out=src/(name+'.pdf')
    if not out.exists() or (name=='annual2025' and out.stat().st_size<1000000):
        r=requests.get(url,headers=headers,timeout=60)
        print(name,r.status_code,r.headers.get('content-type'),len(r.content),r.content[:5])
        out.write_bytes(r.content)
    else: print(name,'exists',out.stat().st_size)
for name in ['annual2025','audit2025','q1_2026']:
    pdf=src/(name+'.pdf')
    print('\nPDF',name,pdf.stat().st_size)
    with pdfplumber.open(pdf) as p:
        print('pages',len(p.pages))
        for i in [0,1,2,3,4,5,10,20,30,50,80,100,120]:
            if i < len(p.pages):
                text=(p.pages[i].extract_text() or '')[:400].replace('\n',' | ')
                print('PAGE',i+1,text)

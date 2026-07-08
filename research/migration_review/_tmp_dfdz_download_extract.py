import requests, pathlib, re, json, pdfplumber
base=pathlib.Path.cwd()
src=base/'source_docs'
src.mkdir(exist_ok=True)
files={
 'annual2025':'finalpage/2026-04-24/1225161861.PDF',
 'q1_2026':'finalpage/2026-04-29/1225233627.PDF',
 'dividend2025':'finalpage/2026-07-01/1225399607.PDF',
 'profit_dist':'finalpage/2026-04-24/1225161863.PDF',
 'esg2025':'finalpage/2026-04-24/1225161872.PDF',
}
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
for name,path in files.items():
    url='http://static.cninfo.com.cn/'+path
    out=src/(name+'.pdf')
    if not out.exists() or out.stat().st_size<1000:
        r=requests.get(url,headers=headers,timeout=30)
        print(name,r.status_code,r.headers.get('content-type'),len(r.content),r.content[:5])
        out.write_bytes(r.content)
    else:
        print(name,'exists',out.stat().st_size)
# Extract selected text snippets/pages counts
for name in ['annual2025','q1_2026','dividend2025']:
    pdf=src/(name+'.pdf')
    print('\nPDF',name,pdf.stat().st_size)
    with pdfplumber.open(pdf) as p:
        print('pages',len(p.pages))
        text='\n'.join((page.extract_text() or '') for page in p.pages[:min(20,len(p.pages))])
        print(text[:2000].replace('\n',' | '))

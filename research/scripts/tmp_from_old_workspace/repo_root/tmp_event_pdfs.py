import requests, pathlib, pdfplumber, json
base='http://static.cninfo.com.cn/'
items=[('product_bid_20260508','finalpage/2026-05-08/1225281351.PDF'),('dividend_20260618','finalpage/2026-06-18/1225376136.PDF')]
out=pathlib.Path('data_sources'); out.mkdir(exist_ok=True)
for name,path in items:
    pdf=out/(name+'.pdf')
    if not pdf.exists():
        r=requests.get(base+path,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
        print(name,r.status_code,len(r.content))
        pdf.write_bytes(r.content)
    text=[]
    with pdfplumber.open(pdf) as p:
        for page in p.pages:
            text.append(page.extract_text() or '')
    (out/(name+'.txt')).write_text('\n'.join(text),encoding='utf-8')
    print('---',name)
    print('\n'.join(text)[:3000])
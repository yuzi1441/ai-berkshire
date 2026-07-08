import pdfplumber, re, pathlib, json
base=pathlib.Path('data/eastone_000682_raw')
for pdf in ['1225161855.pdf','1225233627.pdf']:
    p=base/pdf
    txt=[]
    with pdfplumber.open(p) as doc:
        print(pdf, len(doc.pages))
        for i,page in enumerate(doc.pages):
            text=page.extract_text() or ''
            if any(k in text for k in ['主营业务','分行业','分产品','分地区','营业收入','研发投入','智能电网','虚拟电厂','储能','员工']):
                txt.append(f'\n---page {i+1}---\n'+text[:2500])
    out=base/(pdf+'.snips.txt')
    out.write_text('\n'.join(txt),encoding='utf-8')
    print('wrote',out,len(txt))

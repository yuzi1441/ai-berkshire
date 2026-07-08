import pdfplumber, re, pathlib, json, sys
files=list(pathlib.Path('sources/002270').glob('*.pdf'))
for fp in sorted(files):
    if '摘要' in fp.name or '半年' in fp.name or '三季' in fp.name: continue
    print('\n===== FILE',fp.name,'=====')
    with pdfplumber.open(str(fp)) as pdf:
        for i,p in enumerate(pdf.pages[:25]):
            txt=p.extract_text() or ''
            if '六、主要会计数据和财务指标' in txt or '主要会计数据和财务指标' in txt or '主要财务数据' in txt:
                print('--- page',i+1,'---')
                print(txt[:3500].replace('\uf052','').replace('\uf0a3',''))

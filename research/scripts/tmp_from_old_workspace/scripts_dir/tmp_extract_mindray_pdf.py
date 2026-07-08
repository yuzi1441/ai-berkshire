from pathlib import Path
import pdfplumber, re
for fn in ['sources/mindray/mindray-2025-annual.pdf','sources/mindray/mindray-2026-q1.pdf']:
    print('\n###',fn)
    with pdfplumber.open(fn) as pdf:
        print('pages', len(pdf.pages))
        text='\n'.join((p.extract_text() or '') for p in pdf.pages)
    out=Path(fn).with_suffix('.txt')
    out.write_text(text,encoding='utf-8')
    for pat in ['营业收入','归属于上市公司股东的净利润','生命信息与支持','体外诊断','医学影像','研发投入','境外','总股本','分红','现金分红']:
        idx=text.find(pat)
        print('PAT',pat,idx)
        if idx!=-1:
            print(text[max(0,idx-300):idx+800].replace('\n',' ')[:1200])

from pathlib import Path
import pdfplumber, re, json
base=Path.cwd()/'sources'
out={}
for name,pages in {'2025AnnualReportA.pdf':[9,10,11,12,13,17,19,20,21,22,23,24,25,26,27,28,29], '2026Q1_A.pdf':list(range(0,25))}.items():
    p=base/name
    texts=[]
    with pdfplumber.open(p) as pdf:
        for idx in pages:
            if idx < len(pdf.pages):
                txt=pdf.pages[idx].extract_text(x_tolerance=1, y_tolerance=3) or ''
                texts.append(f'--- PAGE {idx+1} ---\n{txt}')
    (base/(name+'.txt')).write_text('\n\n'.join(texts), encoding='utf-8')
    print('wrote', base/(name+'.txt'))

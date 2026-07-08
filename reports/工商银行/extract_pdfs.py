from pathlib import Path
import pdfplumber, re
files = ['Announce20260429_5.pdf','2025AnnualReportA.pdf']
for f in files:
    out = Path(f).with_suffix('.txt')
    texts=[]
    with pdfplumber.open(f) as pdf:
        print(f, 'pages', len(pdf.pages))
        for i,p in enumerate(pdf.pages):
            txt = p.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n--- PAGE {i+1} ---\n'+txt)
    out.write_text('\n'.join(texts), encoding='utf-8')
    print('wrote', out, out.stat().st_size)

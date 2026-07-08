from pathlib import Path
import pdfplumber, re, sys
sys.stdout.reconfigure(encoding='utf-8')
p=Path('source_pdfs/hengrui_2025_annual.pdf')
keywords=['创新药销售收入','对外许可','收入结构','主要产品','研发管线','集采','已上市创新药','核心产品','国家医保','肿瘤','麻醉','造影剂','收入确认']
with pdfplumber.open(str(p)) as pdf:
    texts=[]
    for i,page in enumerate(pdf.pages):
        txt=page.extract_text() or ''
        for kw in keywords:
            if kw in txt:
                texts.append((i+1,kw,txt))
                break
    print('matches',len(texts))
    for pg,kw,txt in texts[:30]:
        print('\n===== page',pg,'kw',kw,'=====')
        # lines with any keyword context
        lines=txt.splitlines()
        for j,line in enumerate(lines):
            if any(k in line for k in keywords):
                start=max(0,j-2); end=min(len(lines),j+4)
                print('\n'.join(lines[start:end]))
                print('---')

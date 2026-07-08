import pdfplumber, pathlib
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
with pdfplumber.open(p) as pdf:
    for i,page in enumerate(pdf.pages, start=1):
        text=page.extract_text() or ''
        if '普通股股东总数' in text or '前10名股东' in text or '许继集团有限公司' in text:
            print('PAGE',i)
            print(text[:2500])

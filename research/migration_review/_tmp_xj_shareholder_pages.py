import pdfplumber, pathlib, re
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
for num in range(40,53):
    with pdfplumber.open(p) as pdf:
        text=pdf.pages[num-1].extract_text() or ''
    print(f'===== PAGE {num} =====')
    print(text[:5000])

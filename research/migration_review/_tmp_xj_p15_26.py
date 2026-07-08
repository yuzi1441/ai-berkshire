import pdfplumber, pathlib
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
with pdfplumber.open(p) as pdf:
    for num in range(15,27):
        text=pdf.pages[num-1].extract_text() or ''
        print(f'\n===== PAGE {num} =====')
        print(text)

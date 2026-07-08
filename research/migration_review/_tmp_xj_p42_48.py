import pdfplumber, pathlib
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
with pdfplumber.open(p) as pdf:
    for num in [42,43,44,45,46,47,48]:
        text=pdf.pages[num-1].extract_text() or ''
        print(f'===== PAGE {num} =====')
        print(text)

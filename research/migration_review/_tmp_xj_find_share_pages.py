import pdfplumber, pathlib
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
with pdfplumber.open(p) as pdf:
    for num in range(30,36):
        text=pdf.pages[num-1].extract_text() or ''
        if '股东' in text or '前10' in text or '实际控制人' in text or '控股股东' in text:
            print(f'===== PAGE {num} =====')
            print(text)

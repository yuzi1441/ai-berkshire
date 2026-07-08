import pdfplumber, pathlib, re
p=pathlib.Path('source_docs/xj-electric/xj_2025_annual.pdf')
want_pages = list(range(10,20)) + [24,25,26,27,28,29,30,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,60,80,100,110,120,130,140,150,160,170,180,190,195,196,197,198,199,200]
with pdfplumber.open(p) as pdf:
    for num in want_pages:
        if 1<=num<=len(pdf.pages):
            text=pdf.pages[num-1].extract_text() or ''
            print(f'\n===== PAGE {num} =====')
            print(text[:4000])

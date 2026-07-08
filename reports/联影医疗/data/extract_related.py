import pdfplumber,pathlib
p=pathlib.Path('data/united_imaging_2025_ar.pdf')
with pdfplumber.open(p) as pdf:
    out=[]
    for n in range(348,359):
        out.append(f'\n--- PAGE {n} ---\n'+(pdf.pages[n-1].extract_text() or ''))
pathlib.Path('data/pages_348_358.txt').write_text('\n'.join(out),encoding='utf-8')

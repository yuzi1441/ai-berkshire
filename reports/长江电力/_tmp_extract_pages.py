import pdfplumber, pathlib
pdf='sources/annual_cypc.pdf'
out=pathlib.Path('sources/annual_key_pages.txt')
with pdfplumber.open(pdf) as p:
    parts=[]
    for i in list(range(5,21))+list(range(23,34))+[46,47,49,84,86,186,208,257]:
        if i<=len(p.pages):
            text=p.pages[i-1].extract_text(x_tolerance=1, y_tolerance=3) or ''
            parts.append(f'\n===== PAGE {i} =====\n{text[:5000]}')
    out.write_text('\n'.join(parts), encoding='utf-8')
print(out, out.stat().st_size)
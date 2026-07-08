import pdfplumber, pathlib
pdf='sources/002270/2025AR_1224986242.pdf'
sel=list(range(8,31))+list(range(53,78))+list(range(145,180))+list(range(205,226))
out=pathlib.Path('data/huaming_002270/annual_selected_pages.txt')
with pdfplumber.open(pdf) as p:
    chunks=[]
    for n in sel:
        if n<=len(p.pages):
            text=p.pages[n-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
            chunks.append(f'\n\n===== PAGE {n} =====\n{text}')
    out.write_text(''.join(chunks),encoding='utf-8')
print(out, out.stat().st_size)

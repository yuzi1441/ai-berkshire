import pdfplumber, pathlib
for f in ['四方股份-2026Q1-新浪.PDF','_tmp_2025.pdf']:
    print('FILE', f, pathlib.Path(f).stat().st_size)
    with pdfplumber.open(f) as pdf:
        print('pages', len(pdf.pages))
        for i in range(min(3,len(pdf.pages))):
            text=pdf.pages[i].extract_text(x_tolerance=1, y_tolerance=3) or ''
            print('---page',i+1,'---')
            print(text[:2000])

import pdfplumber, pathlib, re, json
pdf=pathlib.Path.cwd()/'source_docs'/'annual2025.pdf'
with pdfplumber.open(pdf) as p:
    for page_no in [7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,81,82,83,84,85,86,87,88,89,90]:
        if page_no<=len(p.pages):
            text=p.pages[page_no-1].extract_text(x_tolerance=1, y_tolerance=3) or ''
            out=pathlib.Path.cwd()/'source_docs'/f'annual_p{page_no}.txt'
            out.write_text(text,encoding='utf-8')
            print('WROTE',out.name,len(text))

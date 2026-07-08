import pdfplumber, pathlib
for pdfname in ['q1_2026.pdf','profit_dist.pdf','dividend2025.pdf']:
    pdf=pathlib.Path.cwd()/'source_docs'/pdfname
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages,1):
            text=page.extract_text() or ''
            (pathlib.Path.cwd()/'source_docs'/f'{pdfname[:-4]}_p{i}.txt').write_text(text,encoding='utf-8')
            print(pdfname,i,len(text),text[:300].replace('\n',' | '))

import pdfplumber, pathlib
for name in ['q1.pdf']:
    p=pathlib.Path('data')/name
    with pdfplumber.open(p) as pdf:
        text=[]
        for i,page in enumerate(pdf.pages):
            text.append(f'\n--- PAGE {i+1} ---\n'+(page.extract_text() or ''))
    pathlib.Path('data/q1.txt').write_text('\n'.join(text),encoding='utf-8')
print('done')

import pdfplumber, pathlib
pdf=pathlib.Path('data/长江电力/q1_2026.pdf')
with pdfplumber.open(pdf) as p:
 print('pages',len(p.pages))
 for i,page in enumerate(p.pages,1):
  txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
  print('\n---P',i,'---')
  print(txt[:3500])

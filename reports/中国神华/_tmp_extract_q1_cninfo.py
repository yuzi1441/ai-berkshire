import pdfplumber, pathlib
path=pathlib.Path('reports/中国神华/sources/q1_2026_cninfo.pdf')
with pdfplumber.open(path) as pdf:
 print('pages',len(pdf.pages))
 for i,p in enumerate(pdf.pages):
  print('\n---page',i+1,'---')
  print((p.extract_text() or '')[:2500])
  for ti,tab in enumerate(p.extract_tables()[:3]):
   print('TABLE',ti)
   for row in tab[:15]: print(row)

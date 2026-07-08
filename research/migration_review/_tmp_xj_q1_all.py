import pdfplumber, pathlib
for fname in ['xj_2026_q1.pdf']:
 p=pathlib.Path('source_docs/xj-electric')/fname
 with pdfplumber.open(p) as pdf:
  for i,page in enumerate(pdf.pages, start=1):
   text=page.extract_text() or ''
   print(f'===== {fname} PAGE {i} =====')
   print(text)

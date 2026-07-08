import pdfplumber, re, pathlib, json
base=pathlib.Path('sources')
for name in ['annual2025.pdf','q1_2026.pdf']:
 p=base/name
 print('---', name, p.stat().st_size)
 with pdfplumber.open(p) as pdf:
  print('pages', len(pdf.pages))
  text='\n'.join((page.extract_text(x_tolerance=1, y_tolerance=3) or '') for page in pdf.pages[:5])
  print(text[:3000])

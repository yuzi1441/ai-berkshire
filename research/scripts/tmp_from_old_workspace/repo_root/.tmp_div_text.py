import pdfplumber, pathlib
for p in pathlib.Path('sources/huaming').glob('*利润分配*.PDF'):
 print('\n###',p.name)
 with pdfplumber.open(p) as pdf:
  text='\n'.join((page.extract_text() or '') for page in pdf.pages[:4])
  print(text[:2200])

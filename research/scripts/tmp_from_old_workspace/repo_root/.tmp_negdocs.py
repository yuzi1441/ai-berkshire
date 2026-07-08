import pdfplumber, pathlib
for pat in ['*诉讼事项*.PDF','*处罚*.PDF','*问询函*回复*.PDF','*监管*.PDF','*减持*.PDF']:
 for p in pathlib.Path('sources/huaming').glob(pat):
  print('\n###',p.name)
  try:
   with pdfplumber.open(p) as pdf:
    text='\n'.join((page.extract_text() or '') for page in pdf.pages[:8])
    print(text[:3500])
  except Exception as e: print(e)

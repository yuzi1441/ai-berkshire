import pdfplumber, pathlib
p=pathlib.Path('sources/huaming/1224986242_2025年年度报告.PDF')
terms=['境外收入','分地区','国外','出口','海外','外销','主营业务分地区']
with pdfplumber.open(p) as pdf:
 for i,page in enumerate(pdf.pages):
  text=page.extract_text() or ''
  if any(t in text for t in terms):
   print('\nPAGE',i+1)
   compact='\n'.join(text.split('\n'))
   print(compact[:5000])

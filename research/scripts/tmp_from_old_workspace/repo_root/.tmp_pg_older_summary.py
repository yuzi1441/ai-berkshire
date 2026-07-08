import pdfplumber, pathlib, re, json
for year in [2023,2022,2021]:
 p=pathlib.Path(f'sources/pinggao/annual{year}.pdf')
 print('\n====',year,'====')
 with pdfplumber.open(p) as pdf:
  for pi in range(5,9):
   text=pdf.pages[pi].extract_text() or ''
   print('\n---page',pi+1,'---')
   print(text[:5000])

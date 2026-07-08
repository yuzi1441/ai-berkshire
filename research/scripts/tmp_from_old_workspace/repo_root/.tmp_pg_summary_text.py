import pdfplumber, pathlib
for year in [2025,2024,2023,2022,2021]:
 p=pathlib.Path(f'sources/pinggao/annual{year}.pdf')
 with pdfplumber.open(p) as pdf:
  print('\n====',year,'pages around summary====')
  for pi in range(5,8):
   if pi>=len(pdf.pages): continue
   text=pdf.pages[pi].extract_text() or ''
   print('\n---page',pi+1,'---')
   print(text[:4500])

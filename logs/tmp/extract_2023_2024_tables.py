import pdfplumber, pathlib
for y,pages in [('2023',[5,6,7,8]),('2024',[6,7,8,9])]:
 pdf=pathlib.Path(rf'E:\ai-berkshire\research\source_docs\jiangnan-chemical\jiangnan-chemical-{y}-annual.pdf')
 print('\n###', y)
 with pdfplumber.open(pdf) as p:
  for idx in pages:
   print('--- page', idx+1)
   for table in p.pages[idx].extract_tables():
    for row in table[:20]:
     print(' | '.join([(c or '').replace('\n',' ') for c in row]))
    print('---tableend')

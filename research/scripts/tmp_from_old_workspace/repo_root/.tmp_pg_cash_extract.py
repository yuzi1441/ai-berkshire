import pdfplumber, pathlib, re, json
for year in [2025,2024,2023,2022,2021]:
 print('\n====',year,'cash====')
 text='\n'.join((p.extract_text() or '') for p in pdfplumber.open(pathlib.Path(f'sources/pinggao/annual{year}.pdf')).pages)
 for pat in ['经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资']:
  vals=[]
  for m in re.finditer(re.escape(pat), text):
   sn=text[m.start():m.start()+220].replace('\n',' ')
   vals.append(sn)
  print('pat',pat,'count',len(vals))
  for sn in vals[:5]: print(sn)

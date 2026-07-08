import pdfplumber, pathlib, re, json
for year in [2025,2024,2023,2022,2021]:
 p=pathlib.Path(f'sources/pinggao/annual{year}.pdf')
 if not p.exists(): continue
 print('\n====',year,'====')
 with pdfplumber.open(p) as pdf:
  for pi in range(min(12,len(pdf.pages))):
   text=pdf.pages[pi].extract_text() or ''
   if '主要会计数据' in text or '主要财务指标' in text or '营业收入' in text and '净利润' in text:
    print('---page',pi+1,'---')
    print(text[:3000])

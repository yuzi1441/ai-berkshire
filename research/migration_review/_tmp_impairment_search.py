import pdfplumber, pathlib
for pdf in ['data/长江电力/annual2025.pdf','data/长江电力/annual2024.pdf']:
 print('\n===',pdf,'===')
 with pdfplumber.open(pdf) as p:
  for i,page in enumerate(p.pages,1):
   txt=page.extract_text() or ''
   if '重组注入标的资产减值测试' in txt or '重大资产重组注入标的资产' in txt or '减值测试' in txt:
    idx=txt.find('减值测试')
    print('P',i,txt[max(0,idx-600):idx+1200].replace('\n',' ')[:1800])

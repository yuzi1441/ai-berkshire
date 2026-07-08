import pdfplumber, pathlib, re
src=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\中国神华\sources')
for pdf in ['2025_annual.pdf','2026_q1.pdf']:
 with pdfplumber.open(src/pdf) as p:
  print(pdf, len(p.pages))
  for page_no in ([8,9,10,31,32,33,34,35,36,37,38,39,40,41,75,76,77,78,79,80,81] if 'annual' in pdf else [2,3,4,5,6,7,8,9,10]):
   if page_no<=len(p.pages):
    text=p.pages[page_no-1].extract_text() or ''
    out=src/f'{pdf}_page{page_no}.txt'
    out.write_text(text,encoding='utf-8')
    print(out)
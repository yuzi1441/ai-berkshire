import pdfplumber, pathlib, re, json
banks=['ICBC','CCB','ABC','BOC','BOCOM','PSBC','CMB']
for b in banks:
 print('\n###',b)
 with pdfplumber.open(pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf') as pdf:
  for i,p in enumerate(pdf.pages):
   text=p.extract_text() or ''
   if any(k in text for k in ['科技金融','制造业','普惠','小微','五篇大文章','战略']):
    print('--page',i+1)
    for line in text.split('\n'):
     if any(k in line for k in ['科技金融','制造业','普惠','小微','五篇大文章','战略','绿色','养老','数字']):
      print(line)

import pdfplumber
for fn in ['2024_annual_1223145398.PDF','2025_annual_1225117829.PDF']:
 print('\n====',fn,'====')
 pdf=pdfplumber.open('data/source/siyuan/'+fn)
 for i,p in enumerate(pdf.pages):
  text=p.extract_text() or ''
  if '2025年' in text and ('目标' in text or '规划' in text or '经营计划' in text or '收入' in text) and i<60:
   print('\n---page',i+1,'---')
   print(text[:3000])
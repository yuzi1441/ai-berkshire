import pdfplumber,re
with pdfplumber.open('sources/沪电股份/2025AR.pdf') as pdf:
 for i,p in enumerate(pdf.pages):
  text=p.extract_text() or ''
  if '单位：元' in text and '营业收入' in text and '营业成本' in text and '毛利率' in text and ('分行业' in text or '分产品' in text or 'PCB' in text):
   print('\n--- PAGE',i+1,'---')
   print(text[:5000].replace('\n',' | '))

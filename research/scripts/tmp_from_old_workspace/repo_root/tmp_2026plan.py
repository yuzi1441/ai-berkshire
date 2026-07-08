import pdfplumber
pdf=pdfplumber.open('data/source/siyuan/2025_annual_1225117829.PDF')
for i,p in enumerate(pdf.pages):
 text=p.extract_text() or ''
 if '2026年度' in text or '2026年' in text and '经营目标' in text:
  print('\n---page',i+1,'---')
  print(text[:3500])
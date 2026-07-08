import pdfplumber
for fn in ['ir_20260511_12310579.PDF','ir_20260116_11922323.PDF','ir_20251106_11834400.PDF']:
 print('\n====',fn,'====')
 pdf=pdfplumber.open('data/source/siyuan/'+fn)
 for i,p in enumerate(pdf.pages):
  text=p.extract_text() or ''
  print('\n---p',i+1,'---')
  print(text[:2500])
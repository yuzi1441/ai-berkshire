import pdfplumber
pages=[11,12,13,21,22,23,24,25,26,27,28,29,30,31,32,69,70,71,72,73,86,87,88,89,90,152,153,154,155,156,157,158,159,160,161,162,163,276]
with pdfplumber.open('icbc_2025_annual_en.pdf') as p:
 for i in pages:
  if i<1 or i>len(p.pages): continue
  txt=p.pages[i-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
  print('\n---PAGE',i,'---')
  print(txt[:4500])
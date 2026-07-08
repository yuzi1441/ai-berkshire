import pdfplumber
with pdfplumber.open('icbc_2026_q1_en.pdf') as p:
 for i in range(9,15):
  txt=p.pages[i-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
  print('\n---PAGE',i,'---')
  print(txt[:5000])
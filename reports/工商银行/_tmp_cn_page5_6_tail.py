import pdfplumber
with pdfplumber.open('icbc_2026_q1_cn_A.pdf') as p:
 for idx in [4,5]:
  txt=p.pages[idx].extract_text(x_tolerance=1,y_tolerance=3) or ''
  print('\n---PAGE',idx+1,'---')
  print(txt[-1200:])
import pdfplumber
with pdfplumber.open('icbc_2026_q1_cn_A.pdf') as p:
 txt=p.pages[4].extract_text(x_tolerance=1,y_tolerance=3) or ''
 print(txt)
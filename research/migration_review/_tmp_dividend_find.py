import pdfplumber
f='reports/工商银行/sources/ICBC_2025_Annual_A.pdf'
terms=['1.689','1.414','人民币1.689','现金股息','派息','每十股','每 10 股','10股']
with pdfplumber.open(f) as pdf:
 for i,p in enumerate(pdf.pages):
  text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
  if any(t in text for t in terms):
   print('\nPAGE',i+1,[t for t in terms if t in text])
   for t in terms:
    idx=text.find(t)
    if idx!=-1:
     print(text[max(0,idx-400):idx+1000].replace('\n',' | ')[:1500])
     break
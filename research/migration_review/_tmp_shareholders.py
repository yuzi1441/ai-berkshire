import pdfplumber
f='reports/工商银行/sources/ICBC_2025_Annual_A.pdf'
terms=['中央汇金','财政部','香港中央结算','主要股东','股东总数','持股情况']
with pdfplumber.open(f) as pdf:
 for i,p in enumerate(pdf.pages):
  text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
  if any(t in text for t in terms):
   if i+1>=88 and i+1<=95:
    print('\nPAGE',i+1,[t for t in terms if t in text])
    print(text.replace('\n',' | ')[:2500])
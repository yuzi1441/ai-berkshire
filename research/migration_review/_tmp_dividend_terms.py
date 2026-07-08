import pdfplumber,re,json
f='reports/工商银行/sources/ICBC_2025_Annual_A.pdf'
terms=['派发现金股息','现金股息','每10股','分红派息','利润分配方案','股息','现金分红']
with pdfplumber.open(f) as pdf:
 for i,p in enumerate(pdf.pages):
  text=p.extract_text() or ''
  if any(t in text for t in terms):
   if i+1 in range(1,300):
    # show relevant pages but cap
    found=[t for t in terms if t in text]
    print('\nPAGE',i+1,found)
    for t in found[:2]:
     idx=text.find(t)
     print(text[max(0,idx-400):idx+1000].replace('\n',' | ')[:1400])
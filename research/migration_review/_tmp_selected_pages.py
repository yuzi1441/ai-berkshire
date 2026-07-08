import pdfplumber,re,json
f='reports/工商银行/sources/ICBC_2025_Annual_A.pdf'
with pdfplumber.open(f) as pdf:
 for page in [37,41,44,45,46,47,48,49,50,51,52,53,54,55,56,84,85,113,114,115,116,117,118,119]:
  if page<=len(pdf.pages):
   text=pdf.pages[page-1].extract_text(x_tolerance=1,y_tolerance=3) or ''
   print('\n=== PAGE',page,'===')
   print(text.replace('\n',' | ')[:2500])
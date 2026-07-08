import pdfplumber,re
with pdfplumber.open('sources/沪电股份/2025AR.pdf') as pdf:
 for page_no in [16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50]:
  text=pdf.pages[page_no-1].extract_text() or ''
  if any(x in text for x in ['汽车应用领域','工业控制','主营业务','营业收入构成','占营业收入','前五名客户','销售量','采购']):
   print('\n--- PAGE',page_no,'---')
   print(text[:3500].replace('\n',' | '))

import pdfplumber
with pdfplumber.open('sources/沪电股份/2025AR.pdf') as pdf:
 for page_no in [22,23,24,25,26,27,28,29,30]:
  text=pdf.pages[page_no-1].extract_text() or ''
  print('\n--- PAGE',page_no,'---')
  print(text[:4000].replace('\n',' | '))

import pdfplumber
pdf=pdfplumber.open('data/source/siyuan/2025_annual_1225117829.PDF')
for page in [38,39,40,41,42,43]:
 text=pdf.pages[page-1].extract_text() or ''
 print('\n--- PAGE',page,'---')
 print(text)
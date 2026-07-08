import pdfplumber
pdf=pdfplumber.open('data/source/siyuan/2025_annual_1225117829.PDF')
for num in range(15,24):
 text=pdf.pages[num-1].extract_text() or ''
 print('\n--- PAGE',num,'---')
 print(text[:4500])
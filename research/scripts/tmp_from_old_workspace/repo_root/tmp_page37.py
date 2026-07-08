import pdfplumber
pdf=pdfplumber.open('data/source/siyuan/2025_annual_1225117829.PDF')
text=pdf.pages[36].extract_text() or ''
print(text)
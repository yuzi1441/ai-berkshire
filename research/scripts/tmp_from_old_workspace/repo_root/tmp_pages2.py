import pdfplumber
pdf=pdfplumber.open('data/source/siyuan/2025_annual_1225117829.PDF')
for num in range(35,47):
    text=pdf.pages[num-1].extract_text() or ''
    print('\n--- PAGE',num,'---')
    print(text.replace('\n',' ')[:5000])
import pdfplumber, os
pdf_path=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\hengrui_2025_annual.pdf'
out=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\annual_selected_pages.txt'
pages=[5,6,8,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,95,96,97,98,99,100,101,102,103,104,105,106,107,108,109,110,111,112,113,114,115,121,122,123,124,125,126,127]
with pdfplumber.open(pdf_path) as pdf, open(out,'w',encoding='utf-8') as f:
    for n in pages:
        if n<=len(pdf.pages):
            txt=pdf.pages[n-1].extract_text() or ''
            f.write(f'\n\n=== PAGE {n} ===\n')
            f.write(txt)
print(out)

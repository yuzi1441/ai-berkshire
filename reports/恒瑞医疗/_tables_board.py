import pdfplumber, os
p=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\2026041601648_c.pdf'
with pdfplumber.open(p) as pdf:
    for idx in range(len(pdf.pages)):
        page=pdf.pages[idx]
        print('\nPAGE',idx+1)
        tables=page.extract_tables()
        for ti,table in enumerate(tables):
            print('TABLE',ti)
            for row in table[:20]:
                print(row)

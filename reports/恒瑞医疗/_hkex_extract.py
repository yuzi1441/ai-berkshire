import os, pdfplumber
base=r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs'
for fn in ['2026041601648_c.pdf','2026032600033.pdf']:
    p=os.path.join(base,fn)
    print('\n###',fn)
    with pdfplumber.open(p) as pdf:
        print('pages',len(pdf.pages))
        for i in range(min(6,len(pdf.pages))):
            txt=pdf.pages[i].extract_text() or ''
            print('\n--p',i+1,'--')
            print(txt[:2000])

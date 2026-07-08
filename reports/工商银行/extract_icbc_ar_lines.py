import pdfplumber, pathlib, re
path=pathlib.Path('source_pdfs/ICBC_AR_2025.pdf')
keywords=['净利息收益率','科技金融','普惠金融','制造业','贷款','战略','不良贷款率','拨备覆盖率','净息差']
with pdfplumber.open(path) as pdf:
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        if any(k in text for k in keywords):
            lines=[line for line in text.split('\n') if any(k in line for k in keywords)]
            if lines:
                print('\n--- page',i+1,'---')
                for line in lines[:20]: print(line)

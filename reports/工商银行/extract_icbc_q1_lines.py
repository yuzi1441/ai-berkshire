import pdfplumber, pathlib, re
path=pathlib.Path('source_pdfs/ICBC_Q1_2026.pdf')
with pdfplumber.open(path) as pdf:
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        if any(k in text for k in ['净息差','普惠','制造业','科技金融','营业收入','客户贷款']):
            print('\n--- page',i+1,'---')
            for line in text.split('\n'):
                if any(k in line for k in ['营业收入','利息净收入','归属于母公司','客户贷款','不良贷款率','净息差','普惠','制造业','科技金融','贷款总额','拨备覆盖率','资本充足率','手续费']):
                    print(line)

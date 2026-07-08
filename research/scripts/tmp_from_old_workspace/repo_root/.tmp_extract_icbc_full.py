from pathlib import Path
import pdfplumber, re, json
base=Path('sources/工商银行')
for pdf in ['ICBC-2026Q1.pdf','ICBC-2025AnnualReportA.pdf']:
    path=base/pdf
    alltext=[]
    tables=[]
    with pdfplumber.open(path) as p:
        for pi,page in enumerate(p.pages, start=1):
            txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            alltext.append(f'\n--- PAGE {pi} ---\n'+txt)
            if pi<=30 or pdf.endswith('AnnualReportA.pdf'):
                pass
    text=''.join(alltext)
    (base/(pdf+'.full.txt')).write_text(text,encoding='utf-8')
    print(pdf, 'chars', len(text))
    pats=['营业收入','利息净收入','非利息收入','手续费及佣金净收入','资产减值损失','贷款减值损失','总资产','客户贷款及垫款总额','客户存款','不良贷款余额','不良贷款率','拨备覆盖率','核心一级资本充足率','一级资本充足率','资本充足率','净利息差','净利息收益率','制造业','普惠','科技创新','房地产','地方政府融资平台','对公房地产']
    for pat in pats:
        matches=[m.start() for m in re.finditer(re.escape(pat),text)]
        print('\nPAT',pat,'count',len(matches))
        for idx in matches[:3]:
            print(text[max(0,idx-180):idx+420].replace('\n',' ')[:900])
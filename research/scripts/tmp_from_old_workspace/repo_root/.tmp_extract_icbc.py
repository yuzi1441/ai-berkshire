from pathlib import Path
import pdfplumber, re, json
base=Path('sources/工商银行')
for pdf in ['ICBC-2026Q1.pdf','ICBC-2025AnnualReportA.pdf']:
    path=base/pdf
    print('---', pdf)
    with pdfplumber.open(path) as p:
        print('pages', len(p.pages))
        text='\n'.join(page.extract_text(x_tolerance=1,y_tolerance=3) or '' for page in p.pages[:20])
    out=base/(pdf+'.txt')
    out.write_text(text, encoding='utf-8')
    for pat in ['利息净收入','营业收入','净利润','不良贷款率','拨备覆盖率','资本充足率','净利息收益率','净息差','客户贷款','总资产','归属于母公司股东的净利润']:
        idx=text.find(pat)
        print(pat, idx)
        if idx!=-1:
            print(text[max(0,idx-200):idx+400].replace('\n',' ')[:800])
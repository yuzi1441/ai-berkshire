from pathlib import Path
import pdfplumber, re
pdf=Path('sources/工商银行/ICBC-2025AnnualReportA.pdf')
terms=['逾期贷款','逾期90天','重组贷款','个人住房贷款','个人经营性贷款','贷款五级分类','按行业划分','房地产']
with pdfplumber.open(pdf) as p:
    for pi,page in enumerate(p.pages, start=1):
        txt=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
        if any(t in txt for t in terms):
            if pi>=55 and pi<=78:
                print('\n--- PAGE',pi,'---')
                for t in terms:
                    if t in txt: print('TERM',t)
                print(txt[:3500])
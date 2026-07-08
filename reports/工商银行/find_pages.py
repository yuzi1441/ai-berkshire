from pathlib import Path
import pdfplumber, re
p=Path('sources')/'2025AnnualReportA.pdf'
keywords=['分部信息','公司金融业务','个人金融业务','净利息收入','生息资产','资产质量','房地产业','个人贷款','资本充足率','分红']
with pdfplumber.open(p) as pdf:
    for i,page in enumerate(pdf.pages):
        txt=page.extract_text() or ''
        if any(k in txt for k in keywords):
            if i in range(20,120) or i in range(220,260):
                pass
# print selected likely pages from outline by search first occurrence
for kw in keywords:
    found=[]
    with pdfplumber.open(p) as pdf:
        for i,page in enumerate(pdf.pages):
            txt=page.extract_text() or ''
            if kw in txt:
                found.append(i+1)
                if len(found)>=8: break
    print(kw, found)

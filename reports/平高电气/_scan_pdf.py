from pathlib import Path
import pdfplumber, re, json
pdf_path=Path('_sources/annual_2025.pdf')
with pdfplumber.open(pdf_path) as pdf:
    texts=[]
    for i,p in enumerate(pdf.pages, start=1):
        t=p.extract_text() or ''
        texts.append((i,t))
patterns=['控股股东','实际控制人','中国电气装备','前五名客户','客户集中','关联交易','关联方','应收账款','存货','现金流','可能面对的风险','风险','毛利率','分红','资产减值','有息负债','董事','高级管理人员','薪酬']
for pat in patterns:
    print('\n###',pat)
    hits=[]
    for i,t in texts:
        if pat in t:
            hits.append(i)
    print(hits[:30], 'count', len(hits))

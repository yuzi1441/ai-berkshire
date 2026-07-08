import pdfplumber, pathlib, re
base=pathlib.Path('data/source/siyuan')
annual=base/'2025_annual_1225117829.PDF'
patterns=['第 四 节 公司治理','第四节 公司治理','任职情况','公司董事、监事、高级管理人员','董事、监事、高级管理人员报酬','持股情况','控股股东','实际控制人','关联交易','分红','现金分红','回购','前十名股东','董增平','杨哲嵘','林凌','张强','杨帜华']
with pdfplumber.open(annual) as pdf:
    for i,p in enumerate(pdf.pages):
        text=p.extract_text() or ''
        hits=[pat for pat in patterns if pat in text]
        if hits:
            print('\n--- page',i+1,'hits',hits,'---')
            print(text[:2500].replace('\n',' '))
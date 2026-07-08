import pdfplumber, pathlib, re
pdf_path=pathlib.Path('sources/annual2025.pdf')
terms=['董事、高级管理人员持股变动及薪酬情况','董事、高级管理人员薪酬情况','主要股东','控股股东','实际控制人','关联交易','利润分配','股息','资本开支','董事会致辞','管理层讨论与分析','购买资产','发行股份购买资产','国家能源集团','张长岩','宋静刚','总会计师','高级管理人员']
with pdfplumber.open(pdf_path) as pdf:
    texts=[]
    for i,p in enumerate(pdf.pages):
        text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
        for t in terms:
            if t in text:
                print(f'PAGE {i+1} term {t}')
                snip=text[max(0,text.find(t)-200): text.find(t)+800]
                print(snip.replace('\n',' ')[:1000])
                print('---')

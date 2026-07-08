import pdfplumber, re, pathlib, json
p=pathlib.Path('data/united_imaging_2025_ar.pdf')
terms=['张强','薛敏','董事长','总经理','首席财务官','财务负责人','高级管理人员','董事、监事和高级管理人员','薪酬','利润分配','分红','现金分红','回购','关联交易','实际控制人','控股股东','研发投入','营业收入','归属于上市公司股东','员工','国际化','全球化','承诺','募投','并购']
with pdfplumber.open(p) as pdf:
    for term in terms:
        hits=[]
        for i,page in enumerate(pdf.pages):
            txt=page.extract_text() or ''
            if term in txt:
                idx=txt.find(term)
                sn=txt[max(0,idx-80):idx+180].replace('\n',' | ')
                hits.append((i+1,sn))
                if len(hits)>=5: break
        print('\n##',term)
        for pg,sn in hits: print('P',pg, sn)

from pathlib import Path
import pdfplumber, re, json
pdf='icbc_2025_annual_A.pdf'
terms=['董事及高级管理人员情况','廖林','刘珺','薪酬','关联交易','利润分配','现金分红','张红力','董事长致辞','行长致辞','公司治理报告','股利','不良贷款率','资本充足率']
with pdfplumber.open(pdf) as doc:
    for term in terms:
        print('\n===',term,'===')
        count=0
        for i,p in enumerate(doc.pages):
            text=p.extract_text() or ''
            if term in text:
                count+=1
                snippet=text[max(0,text.find(term)-500):text.find(term)+1200]
                print('PAGE',i+1,'PDF_PAGE_LABEL approx',i+1)
                print(snippet.replace('\n',' ')[:1800])
                if count>=5: break
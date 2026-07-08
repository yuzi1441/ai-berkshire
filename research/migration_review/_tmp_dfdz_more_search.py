import pdfplumber, pathlib
pdf=pathlib.Path.cwd()/'source_docs'/'annual2025.pdf'
terms=['购建固定资产','研发费用','现金分红','每 10 股派','应收账款','存货跌价','营业收入','管理层讨论与分析','董事、监事和高级管理人员报酬']
with pdfplumber.open(pdf) as p:
    texts=[page.extract_text() or '' for page in p.pages]
for term in terms:
    print('\nTERM',term)
    c=0
    for i,text in enumerate(texts):
        if term in text:
            idx=text.find(term)
            print('PAGE',i+1,text[max(0,idx-200):idx+800].replace('\n',' | ')[:1200])
            c+=1
            if c>=5: break

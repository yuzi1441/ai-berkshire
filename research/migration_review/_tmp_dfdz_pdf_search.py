import pdfplumber, pathlib, re, json
pdf=pathlib.Path.cwd()/'source_docs'/'annual2025.pdf'
terms=['主要财务指标','营业收入构成','分行业','分产品','主营业务','智能配用电','输变电自动化','综合能源','虚拟电厂','研发投入','核心竞争力','控股股东','实际控制人','董事、监事和高级管理人员','现金分红','非经常性损益','应收账款','存货','经营活动产生的现金流量净额','市场竞争','技术研发风险']
with pdfplumber.open(pdf) as p:
    alltext=[]
    for i,page in enumerate(p.pages):
        text=page.extract_text() or ''
        alltext.append(text)
    for term in terms:
        print('\nTERM',term)
        found=0
        for i,text in enumerate(alltext):
            if term in text:
                idx=text.find(term)
                snip=text[max(0,idx-300):idx+900].replace('\n',' | ')
                print('PAGE',i+1,snip[:1500])
                found+=1
                if found>=3: break
        if not found: print('not found')

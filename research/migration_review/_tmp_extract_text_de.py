import pdfplumber, pathlib, re, json
base=pathlib.Path('sources')/'东方电子'
terms=['主要会计数据和财务指标','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','分行业','分产品','主营业务','研发投入','应收账款','存货','资产负债表','利润表','现金流量表','公司未来发展的展望','可能面对的风险']
for pdf in base.glob('*.pdf'):
    out=base/(pdf.stem+'.txt')
    texts=[]
    with pdfplumber.open(pdf) as p:
        for i,page in enumerate(p.pages):
            txt=page.extract_text() or ''
            texts.append(f'\n\n---PAGE {i+1}---\n'+txt)
    out.write_text('\n'.join(texts),encoding='utf-8')
    print('wrote',out,'chars',len('\n'.join(texts)))
    text='\n'.join(texts)
    for term in terms:
        idx=text.find(term)
        if idx!=-1:
            page=text[:idx].count('---PAGE ')
            print(pdf.name, term, 'page?', page, 'idx', idx)
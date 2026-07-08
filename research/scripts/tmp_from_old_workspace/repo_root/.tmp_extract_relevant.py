import pdfplumber, pathlib, re
path='sources/沪电股份/沪电股份2025年年度报告.pdf'
keywords=['主营业务分行业','主营业务分产品','营业收入构成','占营业收入','数据通讯','智能汽车','销售量','生产量','库存量','主要销售客户','前五名客户','研发投入','技术创新','核心技术','在建工程','货币资金','应收账款','存货','毛利率','境外','境内','产销量']
with pdfplumber.open(path) as pdf:
    chunks=[]
    for i,p in enumerate(pdf.pages):
        txt=p.extract_text() or ''
        if any(k in txt for k in keywords):
            chunks.append(f'---PAGE {i+1}---\n{txt}')
    pathlib.Path('data/ar2025_relevant_fullpages.txt').write_text('\n\n'.join(chunks),encoding='utf-8')
    print('pages', [int(re.search(r'PAGE (\d+)',c).group(1)) for c in chunks])
    print('chars', sum(len(c) for c in chunks))

import pdfplumber, re, pathlib
base=pathlib.Path(r'E:\ai-berkshire\research\source_docs\jiangnan-chemical')
for pdf in sorted(base.glob('jiangnan-chemical-*-annual.pdf')):
    print('\n###', pdf.name)
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        for i,page in enumerate(p.pages[:40]):
            text=page.extract_text() or ''
            if '主要会计数据' in text or '主要财务指标' in text or '营业收入' in text and '归属于上市公司股东的净利润' in text:
                print('--- page', i+1)
                print(text[:3000])
                break

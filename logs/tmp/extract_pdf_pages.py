import pdfplumber, pathlib
base=pathlib.Path(r'E:\ai-berkshire\research\source_docs\jiangnan-chemical')
for pdf in sorted(base.glob('jiangnan-chemical-*-annual.pdf')):
    print('\n###', pdf.name)
    with pdfplumber.open(pdf) as p:
        for idx in range(5,14):
            if idx < len(p.pages):
                text=p.pages[idx].extract_text() or ''
                if any(k in text for k in ['营业收入','归属于上市公司股东的净利润','基本每股收益']):
                    print('--- page', idx+1)
                    print(text[:5000])

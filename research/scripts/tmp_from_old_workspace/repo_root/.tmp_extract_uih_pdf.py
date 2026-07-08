from pathlib import Path
import pdfplumber, re
base=Path('sources/联影医疗')
for pdf in ['2025年报.pdf','2026Q1.pdf']:
    p=base/pdf
    print('---',pdf, p.exists(), p.stat().st_size if p.exists() else '')
    with pdfplumber.open(p) as doc:
        print('pages', len(doc.pages))
        texts=[]
        for i,page in enumerate(doc.pages):
            txt=page.extract_text(x_tolerance=1, y_tolerance=3) or ''
            texts.append(f'\n--- PAGE {i+1} ---\n'+txt)
        out=base/(pdf+'.txt')
        out.write_text('\n'.join(texts),encoding='utf-8')
        print('wrote', out, 'chars', out.stat().st_size)
        full='\n'.join(texts)
        for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','研发投入','主营业务分析','分行业','分产品','核心竞争力','风险因素','资产负债表','利润表','现金流量表','承诺']:
            print(pat, full.find(pat))

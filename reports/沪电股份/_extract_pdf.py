from pathlib import Path
import pdfplumber, re
for fname in ['source_pdfs/hudian_2025_annual.pdf','source_pdfs/hudian_2026_q1.pdf']:
    print('===== ', fname)
    out=[]
    with pdfplumber.open(fname) as pdf:
        print('pages', len(pdf.pages))
        for i,p in enumerate(pdf.pages):
            text=p.extract_text() or ''
            if any(k in text for k in ['主要会计数据','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','资产总额','负债合计','货币资金','资本性支出','应收账款','存货','研发投入','前五名客户','主营业务']):
                out.append((i+1,text[:3000]))
    Path(fname+'.extract.txt').write_text('\n\n'.join(f'---page {i}---\n{t}' for i,t in out), encoding='utf-8')
    print('matched pages', [i for i,_ in out[:50]], 'count', len(out))

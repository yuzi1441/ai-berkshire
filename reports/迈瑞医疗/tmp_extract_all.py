from pathlib import Path
import pdfplumber, re
files={'q1':'source_pdfs/mindray_2026_q1.pdf','ar':'source_pdfs/mindray_2025_annual.pdf'}
for key,f in files.items():
    text=[]
    with pdfplumber.open(f) as pdf:
        for i,p in enumerate(pdf.pages):
            t=p.extract_text() or ''
            text.append(f'\n---PAGE {i+1}---\n'+t)
    out=Path(f'{key}_text.txt'); out.write_text('\n'.join(text),encoding='utf-8')
    print(key, 'bytes', out.stat().st_size)
    patterns=['营业总收入','营业收入','营业成本','毛利率','销售费用','管理费用','研发费用','财务费用','经营活动产生的现金流量净额','应收账款','存货','货币资金','合同负债','短期借款','资产负债率','现金分红','利润分配','归属于上市公司股东的净利润','扣除非经常性']
    txt='\n'.join(text)
    for pat in patterns:
        m=re.search(pat, txt)
        if m: print(key, pat, 'pos', m.start())

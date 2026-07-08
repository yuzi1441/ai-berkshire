from pathlib import Path
import sys, re, json
try:
    import pdfplumber
    print('pdfplumber ok')
except Exception as e:
    print('pdfplumber missing', e)
    sys.exit(1)
base=Path.cwd()/ 'sources'
for name in ['2025AnnualReportA.pdf','2026Q1_A.pdf']:
    p=base/name
    print('\n==', name, p.stat().st_size)
    with pdfplumber.open(p) as pdf:
        print('pages', len(pdf.pages))
        needles=['经营业绩','利息净收入','净利润','每股收益','不良贷款率','拨备覆盖率','资本充足率','净利息收益率','资产总额','客户贷款及垫款总额','客户存款','归属于母公司股东']
        hits=[]
        for i,page in enumerate(pdf.pages):
            txt=page.extract_text() or ''
            for n in needles:
                if n in txt:
                    hits.append((i+1,n,txt[:1000].replace('\n',' | ')))
                    break
            if len(hits)>=20: break
        for h in hits[:20]: print('PAGE',h[0],h[1],h[2][:600])

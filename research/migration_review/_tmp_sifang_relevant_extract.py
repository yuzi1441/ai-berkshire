from pathlib import Path
import pdfplumber, re, sys, json
out=[]

def add_pdf_extract(pdf_path, label, phrases, max_pages=999):
    with pdfplumber.open(pdf_path) as pdf:
        for i,page in enumerate(pdf.pages[:max_pages], start=1):
            text=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            if any(p in text for p in phrases):
                out.append(f"\n\n## {label} PDF page {i}\n")
                out.append(text[:5000])
                tables=page.extract_tables() or []
                for ti,t in enumerate(tables[:4]):
                    out.append(f"\n### table {ti} rows={len(t)}\n")
                    for row in t[:30]:
                        out.append(' | '.join('' if c is None else str(c).replace('\n',' ') for c in row))

add_pdf_extract(Path('sources/sifang/2025_annual_sse_real.pdf'),'annual',[
 '主营业务分行业','主营业务分产品','主营业务分地区','营业收入和营业成本','前五名客户','前五名供应商','研发投入','主要研发项目','主要控股参股公司','董事、监事和高级管理人员','总股本','前10名股东','研发人员','电子式互感器','管理层讨论与分析','报告期内公司所处行业情况','报告期内公司从事的业务情况'
])
add_pdf_extract(Path('sources/sifang/2026_q1_sse_real.pdf'),'q1',[
 '主要会计数据','合并资产负债表','合并利润表','合并现金流量表','前 10 名股东','营业收入','经营活动产生的现金流量净额'
])
add_pdf_extract(Path('sources/sifang/hkex_prospectus_2026.pdf'),'hkex',[
 '按業務線劃分','收入','毛利及毛利率','市場份額','排名','繼電保護','變電站自動化','五大客戶','我們的客戶','我們的供應商','研發','董事及高級管理層','控股股東','電網投資','新型電力系統市場','中國新型電力系統市場','核心技術'
], max_pages=180)
Path('sources/sifang/relevant_extract.md').write_text('\n'.join(out),encoding='utf-8')
print('wrote', Path('sources/sifang/relevant_extract.md').resolve(), len('\n'.join(out)))

from pathlib import Path
base=Path.cwd()
for fname in ['2025AnnualReportA.txt','icbc_2025_annual_A_extract.txt','annual_ranges.txt','annual_more.txt','icbc_2026_q1_A_extract.txt']:
    p=base/fname
    if p.exists():
        txt=p.read_text(encoding='utf-8', errors='ignore')
        print('\n---', fname, len(txt), '---')
        for term in ['董事长致辞','行长致辞','董事长报告','行长报告','廖林','刘珺','分红','资本管理','数字化','风险管理','服务实体','中国特色世界一流']:
            i=txt.find(term)
            print(term, i)

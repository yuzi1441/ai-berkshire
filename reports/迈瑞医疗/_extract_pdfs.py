from pathlib import Path
import pdfplumber, re, json
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\迈瑞医疗')
for pdf in [base/'source_pdfs'/'mindray_2026_q1.pdf', base/'source_pdfs'/'mindray_2025_annual.pdf']:
    print('PDF', pdf.name)
    with pdfplumber.open(pdf) as p:
        print('pages', len(p.pages))
        text='\n'.join((page.extract_text() or '') for page in p.pages)
    out=base/'sources'/(pdf.stem+'.txt')
    out.write_text(text, encoding='utf-8')
    print('chars', len(text), 'out', out)
    for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','生命信息与支持','体外诊断','医学影像','毛利率','分产品']:
        idx=text.find(pat)
        print(pat, idx)
        if idx!=-1: print(text[max(0,idx-150):idx+500].replace('\n',' ')[:700])
        print('---')

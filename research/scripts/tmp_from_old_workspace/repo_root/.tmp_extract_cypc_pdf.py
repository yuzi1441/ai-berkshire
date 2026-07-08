from pathlib import Path
import pdfplumber, re
base=Path('sources/长江电力')
for pdf in ['cypc_2025_annual.pdf','cypc_2026_q1.pdf']:
    p=base/pdf
    txt=base/(pdf+'.txt')
    with pdfplumber.open(p) as doc:
        text='\n'.join(page.extract_text(x_tolerance=1,y_tolerance=3) or '' for page in doc.pages)
    txt.write_text(text,encoding='utf-8')
    print(pdf, 'pages/textlen', len(text), 'saved', txt)
    for pat in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','总资产','装机容量','发电量','溪洛渡','乌东德','白鹤滩','三峡']:
        idx=text.find(pat)
        print(' ', pat, idx, text[idx-80:idx+220].replace('\n',' | ') if idx>=0 else '')

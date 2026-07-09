from pathlib import Path
import pdfplumber, re, json, pandas as pd
rows=[]
for pdf in Path('research/source_docs/大型变压器').glob('*.PDF'):
    code=pdf.name[:6]
    try:
        snippets=[]
        with pdfplumber.open(str(pdf)) as p:
            for i,page in enumerate(p.pages[:15]):
                text=page.extract_text() or ''
                if '营业收入' in text and ('归属于上市公司股东' in text or '净利润' in text):
                    # keep compact lines containing terms
                    lines=[ln for ln in text.splitlines() if any(k in ln for k in ['营业收入','归属于上市公司股东','基本每股收益','加权平均净资产收益率'])]
                    snippets.append({'page':i+1,'lines':lines[:8]})
                    break
        rows.append({'code':code,'pdf':pdf.name,'snippets':snippets})
        print('\n---',code,pdf.name)
        for s in snippets[:1]:
            print('page',s['page']); print('\n'.join(s['lines'][:8]))
    except Exception as e:
        print('ERR',pdf,e)
Path('data/大型变压器/cninfo_pdf_key_snippets_20260708.json').write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

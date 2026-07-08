from pathlib import Path
import pdfplumber, re, json
base=Path('sources/cninfo_hmzb')
for name in ['20260227_2025年年度报告.pdf','20250411_2024年年度报告.pdf','20240411_2023年年度报告.pdf','20230412_2022年年度报告.pdf','20220601_2021年年度报告（修订稿）.pdf','20260427_2026年一季度报告.pdf']:
    p=base/name
    print('\nFILE',p, p.exists(), p.stat().st_size if p.exists() else None)
    if not p.exists(): continue
    with pdfplumber.open(p) as pdf:
        print('pages', len(pdf.pages))
        text='\n'.join((page.extract_text() or '') for page in pdf.pages[:5])
        print(text[:2000].replace('\n',' ')[:2000])
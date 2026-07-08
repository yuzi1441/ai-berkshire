import pdfplumber
from pathlib import Path
pdf=Path('_sources/pinggao_2025_annual_cninfo.pdf')
with pdfplumber.open(pdf) as p:
    for n in [17,18,21,29,114,115,146,153,154,171,179]:
        page=p.pages[n-1]
        print('\n===== PAGE', n, '=====')
        print((page.extract_text() or '')[:4000])

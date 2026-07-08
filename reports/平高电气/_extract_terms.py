import pdfplumber, re
from pathlib import Path
terms=['前五名客户','国家电网','销售额','合同负债','经营计划','126-136','国网','中标','研发投入','国际政治','招标模式']
with pdfplumber.open('_sources/pinggao_2025_annual_cninfo.pdf') as p:
    for i,page in enumerate(p.pages,1):
        t=page.extract_text() or ''
        if any(term in t for term in terms):
            print('\n===== PAGE', i,'=====')
            for line in t.splitlines():
                if any(term in line for term in terms):
                    print(line)

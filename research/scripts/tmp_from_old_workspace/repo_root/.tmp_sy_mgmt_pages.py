from pathlib import Path
import re
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
for page in [35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,63,64,65,66,67,68,69,70,71,72]:
    start=text.find(f'--- page {page} ---')
    if start==-1: continue
    end=text.find(f'--- page {page+1} ---', start+1)
    chunk=text[start:end].replace('\n',' ')
    if any(k in chunk for k in ['董事','董增平','杨小强','前十名股东','实际控制人','控股股东','薪酬','关联交易','商誉','审计意见']):
        print(f'\n--- PAGE {page} ---')
        print(chunk[:3500])

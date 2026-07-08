from pathlib import Path
import re
for fname in ['Announce20260429_5.txt','icbc_2026_q1_A_extract.txt','sources/2026Q1_A.pdf.txt']:
    p=Path(fname)
    if not p.exists(): continue
    text=p.read_text(encoding='utf-8', errors='ignore')
    print('\nFILE',fname,'len',len(text))
    for term in ['营业收入','净利润','不良贷款率','资本充足率','客户贷款','客户存款','分红','核心一级资本','拨备覆盖率']:
        i=text.find(term)
        print('TERM',term,i)
        if i>=0: print(text[max(0,i-200):i+500].replace('\n',' ')[:800])

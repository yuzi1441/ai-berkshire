from pathlib import Path
text=Path('research/source_docs/中航机载/extracted_text/annual_2025_sina.txt').read_text(encoding='utf-8')
for term in ['应收账款','存货','货币资金','短期借款','合同资产','关联方应收项目','关联方应付项目','中航工业集团财务有限责任公司','拆入资金','现金分红']:
    print('\n---',term,'---')
    idx=text.find(term)
    print('idx',idx)
    if idx!=-1: print(text[idx:idx+1200])
q1=Path('research/source_docs/中航机载/extracted_text/q1_2026_sina.txt').read_text(encoding='utf-8')
for term in ['应收账款','存货','货币资金','合同资产','短期借款']:
    print('\n---Q1',term,'---')
    idx=q1.find(term)
    print('idx',idx)
    if idx!=-1: print(q1[idx:idx+800])
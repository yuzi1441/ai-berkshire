from pathlib import Path
s=Path('data/sy_recent_ann_excerpts.txt').read_text(encoding='utf-8')
for term in ['capex_transformer','capex_rugao','投资金额','投资总额','3.82','5.2','扩建变压器','如高高压']:
 print('\nTERM',term)
 idx=s.find(term)
 print('idx',idx)
 if idx!=-1: print(s[max(0,idx-1000):idx+2500])

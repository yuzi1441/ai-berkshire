from pathlib import Path
text=Path('data/raw/sifang/pages_key_utf8.txt').read_text(encoding='utf-8')
terms=['货币资金','应收账款','存货','合同资产','短期借款','负债合计','分配预案','现金分红','研发投入','资产总计']
for term in terms:
 print('\n---',term,'---')
 idx=text.find(term)
 print(idx)
 if idx>=0: print(text[max(0,idx-500):idx+1500])
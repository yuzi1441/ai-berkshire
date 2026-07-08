from pathlib import Path
text=Path('_tmp_annual2025_full.txt').read_text(encoding='utf-8')
for kw in ['利润分配方案','现金分红','每股人民币','每10股','2025 年度末期股息','末期股息','宣派','拟派']:
 print('\n###',kw)
 start=0
 for n in range(3):
  i=text.find(kw,start)
  if i==-1: break
  print('pos',i); print(text[i-800:i+1800]); start=i+1

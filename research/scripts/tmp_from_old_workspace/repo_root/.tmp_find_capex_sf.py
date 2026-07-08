from pathlib import Path
lines=Path('source_docs/四方股份/2025_annual.txt').read_text(encoding='utf-8', errors='ignore').splitlines()
for kw in ['购建固定资产', '资本性支出', '固定资产、无形资产', '应收账款', '合同资产', '存货']:
 print('\nKW',kw)
 c=0
 for i,l in enumerate(lines,1):
  if kw in l:
   print(i,l)
   c+=1
   if c>=10: break

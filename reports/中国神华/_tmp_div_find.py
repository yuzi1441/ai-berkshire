from pathlib import Path
text=Path('_annual_full.txt').read_text(encoding='utf-8')
for kw in ['中期股息','2025年中期','2025 年中期','1.08 元','派发2025年度末期股息','22,340','41,811','418.11','79.1%']:
 print('\n###',kw)
 start=0; c=0
 while True:
  idx=text.find(kw,start)
  if idx<0 or c>=4: break
  print(text[max(0,idx-600):idx+1200].replace('\n',' ')[:2200])
  print('---')
  start=idx+len(kw); c+=1

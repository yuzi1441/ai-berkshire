from pathlib import Path
import re
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for pat in [r'研发投入金额.*', r'研发投入.*2025年.*2024年.*2023年', r'研发人员数量.*', r'研发投入占营业收入比例.*']:
 print('PAT',pat)
 for m in re.finditer(pat,text):
  print(m.start(), text[m.start()-500:m.start()+1000])
  break
# lines around first occurrence of 研发投入金额
lines=text.splitlines()
for i,l in enumerate(lines):
 if '研发投入金额' in l or '研发人员数量' in l or '研发投入占营业收入比例' in l:
  print('LINE',i,l)
  print('\n'.join(lines[max(0,i-10):i+10]))

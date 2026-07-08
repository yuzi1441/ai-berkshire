from pathlib import Path
files=[Path('sources/sse_2025Annual.txt'), Path('sources/sse_2026Q1.txt'), Path('sources/sse_2026H1Power.txt'), Path('sources/tencent_quotes_20260706.txt')]
patterns=['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','总股本','每10股派发','2025年末总股本','总发电量','3071.94','1327.44','27.19','6652']
for f in files:
 print('\n###', f)
 text=f.read_text(encoding='utf-8', errors='ignore')
 for pat in patterns:
  idx=text.find(pat)
  if idx>=0:
   print(f'-- {pat} --')
   print(text[max(0,idx-200):idx+600].replace('\n',' ')[:1000])

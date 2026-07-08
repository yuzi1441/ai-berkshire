from pathlib import Path
# use pypdf extracted full annual? create full if needed
from pypdf import PdfReader
p=Path('_annual_full.txt')
if not p.exists():
 reader=PdfReader('sources/annual2025.pdf')
 p.write_text('\n'.join((page.extract_text() or '') for page in reader.pages),encoding='utf-8')
text=p.read_text(encoding='utf-8')
for kw in ['经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资产支付的现金','购建固定资产','分配股利、利润或偿付利息支付的现金','吸收投资收到的现金','取得借款收到的现金','支付其他与投资活动有关的现金']:
 print('\n###',kw)
 start=0
 c=0
 while True:
  idx=text.find(kw,start)
  if idx<0 or c>=5: break
  print(text[max(0,idx-600):idx+1400].replace('\n',' ')[:2500])
  print('---')
  start=idx+len(kw); c+=1

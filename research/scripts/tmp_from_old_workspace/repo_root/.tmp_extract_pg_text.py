import pdfplumber, re, pathlib
pdf=pathlib.Path('sources/pinggao/annual2025.pdf')
text='\n'.join((p.extract_text() or '') for p in pdfplumber.open(pdf).pages)
patterns=['购建固定','经营活动产生的现金流量净额','投资活动产生的现金流量净额','分配股利','长期借款','资本开支','自由现金流']
for pat in patterns:
 print('\n---',pat,'---')
 for m in re.finditer(pat, text):
  s=max(0,m.start()-300); e=min(len(text),m.end()+500)
  print(text[s:e].replace('\n','\n')[:1200]); break
# save text
pathlib.Path('sources/pinggao/annual2025.txt').write_text(text,encoding='utf-8')
print('wrote txt', len(text))

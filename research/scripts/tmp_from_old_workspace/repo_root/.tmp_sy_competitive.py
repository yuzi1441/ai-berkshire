from pathlib import Path
import re
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
for pat in ['研发费用','研发人员','研发投入','专利','核心技术','中标','市场份额','国家电网','南方电网','主要销售客户','前五名客户','海外收入','境外']:
 print('\n###',pat)
 for m in list(re.finditer(pat,text))[:4]:
  s=max(0,m.start()-450); e=min(len(text),m.start()+1200)
  print(text[s:e].replace('\n',' ')[:1650]); print('---')

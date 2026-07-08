from pathlib import Path
import re
for fn in ['sources/sifang/2025_annual_sse_real.txt','sources/sifang/2026_q1_sse_real.txt','sources/sifang/hkex_prospectus_2026.txt']:
 txt=Path(fn).read_text(encoding='utf-8', errors='ignore')
 print('\n====',fn,'len',len(txt),'====')
 pats=['主要会计数据','营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','分季度主要财务数据','主营业务分行业','主营业务分产品','营业收入和营业成本','前十名股东','研发投入','董事长','总股本','股份总数','主要客户','主要供应商','应收账款','合同资产','综合能源','继电保护','电力电子','分部信息']
 for pat in pats:
  m=re.search(pat,txt)
  if m:
   s=max(0,m.start()-250); e=min(len(txt),m.start()+1200)
   print('\n--',pat,'@',m.start(),'--')
   print(txt[s:e].replace('\n',' ')[:1600])

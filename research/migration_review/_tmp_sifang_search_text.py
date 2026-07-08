from pathlib import Path
import re
files=['sources/sifang/hkex_prospectus_2026.txt','sources/sifang/2025_annual_sse_real.txt','sources/sifang/2026_q1_sse_real.txt']
patterns=['收入','收益','毛利','毛利率','净利润','經調整','2025年','智能电网','智能電網','智慧发电','智慧發電','新能源','储能','儲能','分部','市场份额','排名','第一','继电保护','繼電保護','变电站自动化','變電站自動化','研发','研發','客户','供應商','供应商','董事长','創始','杨奇逊','張偉峰','张伟峰','四方电气','四方電氣','高秀环','高秀環']
for fn in files:
 txt=Path(fn).read_text(encoding='utf-8',errors='ignore')
 print('\n====',fn,'====')
 for pat in patterns:
  locs=[m.start() for m in re.finditer(pat,txt)][:5]
  if locs:
   print(pat,locs[:5])
 print('\nSNIPS')
 for pat in ['收入结构','各产品','按产品','智能電網','智慧發電','新能源及儲能','市场份额','行業排名','中国电力系统','繼電保護','变电站自动化','收益由','毛利率','五大客户','供應商','董事及高级管理层','董事及高級管理層','控股股东','股权结构']:
  m=re.search(pat,txt)
  if m:
   print('\n--',pat,'--')
   print(txt[max(0,m.start()-500):m.start()+2000].replace('\n',' ')[:2500])

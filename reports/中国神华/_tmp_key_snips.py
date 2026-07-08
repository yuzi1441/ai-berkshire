from pathlib import Path
for file in ['_extract_business.txt','_extract_matters.txt','_extract_shareholders.txt','_extract_fiveyear.txt']:
 text=Path(file).read_text(encoding='utf-8')
 print('\nFILE',file)
 for kw in ['2025-2027年度股东回报规划','发行股份及支付现金购买资产','收购杭锦能源','日常关联','持续关连','关联/关连方','国家能源集团','前五大客户','资本开支','2026 年度经营目标','经营目标','分红比例','79.1%','332.1','430.9','207.00','控股股东','无实际控制人','持股比例','国家能源投资集团']:
  idx=text.find(kw)
  if idx>=0:
   print('\n###',kw)
   print(text[max(0,idx-600):idx+1600].replace('\n',' ')[:2500])

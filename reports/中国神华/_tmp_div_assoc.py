from pathlib import Path
for file in ['_extract_matters.txt','_extract_shareholders.txt','_extract_governance.txt','_extract_business.txt']:
 text=Path(file).read_text(encoding='utf-8')
 print('\nFILE',file)
 for kw in ['利润分配政策','利润分配方案','现金分红','派发','每10股','2025年度末期股息','2025年度利润分配','2024年度利润分配','股东回报规划','日常关联交易','持续关连交易','关联交易','关连交易','发行股份及支付现金购买资产','杭锦能源','非经营性占用资金','对外担保']:
  idx=text.find(kw)
  if idx!=-1:
   print('\n###',kw)
   print(text[max(0,idx-700):idx+2200].replace('\n',' ')[:3500])

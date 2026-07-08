from pathlib import Path
text=Path('tmp_annual.txt').read_text(encoding='utf-8',errors='ignore')
terms=['毛利率','分产品','智能变配电系统','智能中压供用电设备','智能电表','充换电','直流输电','营业成本','销售量','采购额','前五名客户','前五名供应商','公司控股股东','实际控制人','董事长','总经理','季侃','任职情况','现金分红']
for term in terms:
 print('\n---',term)
 i=0
 count=0
 while True:
  idx=text.find(term,i)
  if idx<0 or count>=3: break
  print(text[idx:idx+800].replace('\n',' | '))
  i=idx+len(term); count+=1
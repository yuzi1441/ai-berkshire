from pathlib import Path
text=Path('sources/oriental_electronics/2025annual_1225161855.txt').read_text(encoding='utf-8')
keywords=['调度及云化','智能配用电','输变电自动化','新能源及储能','综合能源及虚拟电厂','工业互联网及智能制造','营业收入','分行业','分产品','前五名客户','前五名供应商','研发投入','公司研发人员','现金分红','利润分配','控股股东','实际控制人','资产负债率','应收账款','存货','合同负债','毛利率','董事长']
for kw in keywords:
 print('\n###',kw)
 start=0; count=0
 while True:
  i=text.find(kw,start)
  if i==-1: break
  sn=text[max(0,i-300):i+900].replace('\n',' ')
  print(sn[:1200])
  count+=1; start=i+len(kw)
  if count>=3: break

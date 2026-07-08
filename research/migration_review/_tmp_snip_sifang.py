from pathlib import Path
text=Path('data/raw/sifang/annual.txt').read_text(encoding='utf-8')
patterns=['主营业务分行业','主营业务分产品','主营业务分地区','主营业务分销售模式','分行业','分产品','行业、产品、地区、销售模式','主营业务分析','营业收入构成','电网自动化','发电及企业电力系统','继电保护','新能源','储能','轨道交通','四方电气']
for pat in patterns:
 print('\n====',pat)
 start=0; count=0
 while True:
  idx=text.find(pat,start)
  if idx<0: break
  print('idx',idx)
  print(text[max(0,idx-400):idx+1400])
  start=idx+len(pat); count+=1
  if count>=3: break
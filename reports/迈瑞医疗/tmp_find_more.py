from pathlib import Path
text=Path('source_pdfs/mindray_2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['研发投入','研发人员','现金分红','货币资金','交易性金融资产','短期借款','长期借款','应付债券','总资产','股东信息','前十名股东','李西廷','徐航','成明和','核心竞争力','公司主要从事']:
 print('\n###',term)
 start=0
 count=0
 while True:
  idx=text.find(term,start)
  if idx==-1 or count>=2: break
  print('idx',idx)
  print(text[max(0,idx-500):idx+1200].replace('\n','\n'))
  start=idx+len(term); count+=1

import pdfplumber, re, pathlib, json
for name in ['annual','q1']:
 p=pathlib.Path(f'data/raw/sifang/{name}.pdf')
 print('\n###',name,p)
 with pdfplumber.open(p) as pdf:
  print('pages',len(pdf.pages))
  text='\n'.join((page.extract_text() or '') for page in pdf.pages)
  pathlib.Path(f'data/raw/sifang/{name}.txt').write_text(text,encoding='utf-8')
  for pat in ['营业收入','归属于上市公司股东的净利润','扣除非经常性损益','经营活动产生的现金流量净额','分行业','主营业务','货币资金','资产总计','负债合计','基本每股收益','研发投入','前十名股东']:
   idx=text.find(pat)
   print('\nPAT',pat,'idx',idx)
   if idx!=-1: print(text[max(0,idx-250):idx+800])
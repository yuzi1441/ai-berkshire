import pdfplumber, re, json, os
for name in ['2025_annual','2026_q1']:
 text='\n'.join((p.extract_text(x_tolerance=1,y_tolerance=3) or '') for p in pdfplumber.open(f'reports/华明装备/source_docs/{name}.pdf').pages)
 open(f'reports/华明装备/source_docs/{name}_text.txt','w',encoding='utf-8').write(text)
 print(name,len(text))
 for pat in ['货币资金','应收账款','存货','流动负债合计','负债合计','资产负债率','短期借款','合同负债','研发费用','销售费用','管理费用','财务费用']:
  print('\n',pat)
  for m in list(re.finditer(pat,text))[:4]:
   i=m.start(); print(text[max(0,i-220):i+500].replace('\n',' ')[:800])

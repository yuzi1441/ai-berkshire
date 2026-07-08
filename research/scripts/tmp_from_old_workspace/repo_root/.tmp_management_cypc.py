from pathlib import Path
texts={
'annual':Path('sources/长江电力/cypc_2025_annual.pdf.txt').read_text(encoding='utf-8'),
'q1':Path('sources/长江电力/cypc_2026_q1.pdf.txt').read_text(encoding='utf-8')}
for name,text in texts.items():
 print('\n====',name,'====')
 for pat in ['董事长','总经理','前 10 名股东','中国长江三峡集团有限公司','管理层讨论','董事、监事和高级管理人员','薪酬','董事会','股东总数','实际控制人','控股股东','雇员','员工']:
  print('\n###',pat)
  start=0
  for k in range(3):
   i=text.find(pat,start)
   if i<0: break
   print('IDX',i,text[i-250:i+650].replace('\n',' | '))
   start=i+len(pat)

import pdfplumber, re, os, json
fn='reports/华明装备/source_docs/2025_annual.pdf'
with pdfplumber.open(fn) as pdf:
 text='\n'.join((p.extract_text(x_tolerance=1,y_tolerance=3) or '') for p in pdf.pages)
open('reports/华明装备/source_docs/2025_annual_text.txt','w',encoding='utf-8').write(text)
patterns=['分行业','分产品','分地区','主营业务','电力设备','数控设备','境外','分接开关','销售费用','研发费用','货币资金','应收账款','存货','合同负债','短期借款','资产负债率','现金分红','股东信息','员工持股','海外']
for pat in patterns:
 print('\n###',pat)
 for m in list(re.finditer(pat,text))[:6]:
  i=m.start(); print('---idx',i); print(text[max(0,i-300):i+900].replace('\n',' ')[:1200])

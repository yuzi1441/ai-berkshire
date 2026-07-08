import pdfplumber, re, json, pathlib
files=['annual2025.pdf','q1_2026.pdf','dividend2025.pdf','return_plan_2026_2028.pdf']
base=pathlib.Path('sources/huaming')
patterns=['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','资产总额','归属于上市公司股东的净资产','分接开关','市场占有率','现金分红','每10股','控股股东','肖毅','上海华明','核心竞争力','研发投入','毛利率','净利率','负债合计','货币资金','短期借款','长期借款','员工持股']
for fn in files:
 print('\n===== FILE',fn,'=====')
 with pdfplumber.open(base/fn) as pdf:
  print('pages',len(pdf.pages))
  hits=[]
  for i,p in enumerate(pdf.pages):
   text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
   for pat in patterns:
    if pat in text:
     idx=text.find(pat)
     hits.append((i+1,pat,text[max(0,idx-160):idx+500].replace('\n',' | ')))
  for h in hits[:80]:
   print('--- page',h[0], 'pat',h[1]); print(h[2])
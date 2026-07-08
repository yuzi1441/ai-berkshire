import pdfplumber, pathlib, re, sys
sys.stdout.reconfigure(encoding='utf-8')
base=pathlib.Path('sources/huaming')
for fn in ['annual2025.pdf','q1_2026.pdf','dividend2025.pdf','return_plan_2026_2028.pdf']:
 print('\n====',fn,'====')
 with pdfplumber.open(base/fn) as pdf:
  for page_no in [2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,20,22,30,50,60,80,100,120,140,160,180,200,220]:
   if page_no<=len(pdf.pages):
    text=pdf.pages[page_no-1].extract_text() or ''
    if any(k in text for k in ['营业收入','分接开关','市场占有率','每 10 股','现金分红','控股股东','肖毅','核心竞争力','主要会计数据','股本','前十名股东','员工持股','未来三年']):
     print('\n--page',page_no,'--')
     print(text[:2500])
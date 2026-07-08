import pdfplumber, pathlib, sys
sys.stdout.reconfigure(encoding='utf-8')
for fn in ['annual2025.pdf','q1_2026.pdf','dividend2025.pdf','return_plan_2026_2028.pdf']:
 with pdfplumber.open(pathlib.Path('sources/huaming')/fn) as pdf:
  print('\n====',fn,'pages',len(pdf.pages),'====')
  for i,p in enumerate(pdf.pages, start=1):
   text=p.extract_text() or ''
   for pat in ['现金分红','每 10 股','每10股','分配方案','2026年-2028年','控股股东','实际控制人','肖日明','肖毅','研发投入','专利','有息负债','短期借款','长期借款','商誉','重大缺陷','审计意见','员工持股','股份总数']:
    if pat in text:
     idx=text.find(pat)
     print('\n--page',i,'pat',pat,'--')
     print(text[max(0,idx-600):idx+1200])
     break
import pdfplumber, pathlib, re
for fn in ['mindray_2026_q1.pdf','mindray_2025_annual.pdf']:
 p=pathlib.Path.home()/ 'AppData/Local/Temp/mindray_reports'/fn
 print('\nFILE',fn)
 with pdfplumber.open(p) as pdf:
  print('pages', len(pdf.pages))
  text='\n'.join((page.extract_text() or '') for page in pdf.pages)
  print(text[:3000])
  # keyword contexts
  for kw in ['营业收入','归属于上市公司股东的净利润','经营活动产生的现金流量净额','生命信息与支持','体外诊断','医学影像','国内','国际','境外','主营业务']:
   idx=text.find(kw)
   if idx!=-1: print('\nKW',kw, text[max(0,idx-300):idx+800].replace('\n',' ')[:1200])

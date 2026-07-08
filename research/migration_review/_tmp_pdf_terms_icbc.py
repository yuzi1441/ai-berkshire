import pdfplumber, re, os, json
files=['reports/工商银行/sources/ICBC_2025_Annual_A.pdf','reports/工商银行/sources/ICBC_2026_Q1_A.pdf']
terms=['营业收入','归属于母公司股东的净利润','净利润','资产总额','客户贷款及垫款总额','客户存款','不良贷款率','拨备覆盖率','核心一级资本充足率','资本充足率','净利息收益率','净息差','手续费及佣金净收入','每股收益','每股净资产','现金分红']
out={}
for f in files:
 print('\nFILE',f)
 matches={t:[] for t in terms}
 with pdfplumber.open(f) as pdf:
  print('pages',len(pdf.pages))
  for i,p in enumerate(pdf.pages):
   text=p.extract_text(x_tolerance=1,y_tolerance=3) or ''
   for t in terms:
    if t in text and len(matches[t])<6:
     snip=text[max(0,text.find(t)-250):text.find(t)+600]
     matches[t].append({'page':i+1,'snip':snip})
 out[os.path.basename(f)]=matches
for fn,matches in out.items():
 print('\n====',fn)
 for t,arr in matches.items():
  if arr:
   print('\nTERM',t)
   for a in arr[:3]: print('PAGE',a['page'], a['snip'].replace('\n',' | ')[:1000])
open('reports/工商银行/_tmp_pdf_term_matches.json','w',encoding='utf-8').write(json.dumps(out,ensure_ascii=False,indent=2))
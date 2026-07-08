import pdfplumber
for pdfname in ['pinggao_2026_q1_cninfo.pdf']:
  print('PDF',pdfname)
  with pdfplumber.open('_sources/'+pdfname) as p:
    for i,page in enumerate(p.pages,1):
      t=page.extract_text() or ''
      print('\n===== PAGE',i,'=====')
      print(t[:3000])

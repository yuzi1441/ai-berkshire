import pdfplumber
fp='sources/002270/2026Q1_1225181771.pdf'
with pdfplumber.open(fp) as pdf:
 for i in range(0,5):
  txt=pdf.pages[i].extract_text() or ''
  print('---page',i+1,'---')
  print(txt.replace('\uf052','').replace('\uf0a3','')[:4000])

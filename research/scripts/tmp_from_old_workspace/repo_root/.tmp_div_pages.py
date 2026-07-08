import pdfplumber
for fp in ['sources/002270/2025AR_1224986242.pdf','sources/002270/2024AR_1223055875.pdf','sources/002270/2023AR_1219567826.pdf','sources/002270/2022AR_1216380949.pdf','sources/002270/2021AR_revised_1213571762.pdf']:
 print('\nFILE',fp)
 with pdfplumber.open(fp) as pdf:
  for pg in range(44,63):
   if pg < len(pdf.pages):
    txt=pdf.pages[pg].extract_text() or ''
    if '现金分红' in txt or '利润分配' in txt or '每10股派息' in txt or '回购' in txt:
     print('--- page',pg+1,'---')
     print(txt.replace('\uf052','').replace('\uf0a3','')[:5000])

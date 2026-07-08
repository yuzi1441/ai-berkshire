import pdfplumber, pathlib
for b in ['BOCOM','PSBC','CMB','ICBC','CCB','ABC','BOC']:
 path=pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf'
 print('\n###',b)
 with pdfplumber.open(path) as pdf:
  text='\n'.join((p.extract_text() or '') for p in pdf.pages)
 for key in ['拨备覆盖率','核心一级资本充足率','资本充足率']:
  idx=text.find(key)
  print('--',key,idx)
  if idx!=-1:
   print(text[idx:idx+250].replace('\n',' | '))

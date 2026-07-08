import pdfplumber, pathlib, re
for b in ['ICBC','CCB','ABC','BOC']:
 print('\n###',b)
 with pdfplumber.open(pathlib.Path('source_pdfs')/f'{b}_Q1_2026.pdf') as pdf:
  text='\n'.join((p.extract_text() or '') for p in pdf.pages)
 for key in ['核心一级资本充足率','资本充足率']:
  idx=text.find(key)
  print('--',key,idx,text[idx:idx+180].replace('\n',' | ') if idx!=-1 else '')

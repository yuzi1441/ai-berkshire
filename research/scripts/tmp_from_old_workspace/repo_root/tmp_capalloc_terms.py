from pathlib import Path
text=Path('sources/beigene_management/2025_10k.txt').read_text(encoding='utf-8')
terms=['Amgen', 'Novartis', 'BMS', 'Celgene', 'Hopewell', 'manufacturing', 'capital expenditures', 'Facilities Agreement', 'Sale of Future Royalties', 'royalty', 'dividend', 'repurchase']
for term in terms:
 print('\n===',term,'===')
 start=0; n=0
 while n<3:
  idx=text.lower().find(term.lower(), start)
  if idx==-1: break
  print('idx',idx, text[max(0,idx-500):idx+1700].replace('\n',' ')[:2200])
  start=idx+1; n+=1

from pathlib import Path
for fname in ['2025_10k.txt','2026_q1_10q.txt']:
 text=Path('sources/beigene_management/'+fname).read_text(encoding='utf-8')
 for term in ['Sale of future royalties','sale of future royalty','royalty liability','Facilities Agreement','November 2025']:
  idx=text.lower().find(term.lower())
  print('\n',fname,term,idx)
  if idx!=-1: print(text[max(0,idx-500):idx+1800].replace('\n',' ')[:2300])

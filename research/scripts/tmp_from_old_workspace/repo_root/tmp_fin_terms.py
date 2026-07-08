from pathlib import Path
for fname in ['2025_10k.txt','2026_q1_10q.txt','2024_10k.txt','2023_10k.txt']:
 text=Path('sources/beigene_management/'+fname).read_text(encoding='utf-8')
 print('\n====',fname,'====')
 for term in ['Total revenues','Total revenue','Net product revenues','BRUKINSA product revenue','Net income','Net loss','cash flows from operating activities','operating cash flow','2026 Guidance','2025 Guidance','full year 2026']:
  idx=text.lower().find(term.lower())
  print(term,idx)
  if idx!=-1: print(text[idx:idx+1800].replace('\n',' ')[:1800])

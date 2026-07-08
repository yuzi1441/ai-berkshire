from pathlib import Path
for fname in ['2026_q1_10q.txt','2025_10k.txt','2026_proxy.txt']:
 text=Path('sources/beigene_management/'+fname).read_text(encoding='utf-8')
 for term in ['each ADS represents', '13 ordinary shares', 'American Depositary Share']:
  idx=text.lower().find(term.lower())
  print(fname, term, idx)
  if idx!=-1: print(text[max(0,idx-250):idx+500].replace('\n',' '))

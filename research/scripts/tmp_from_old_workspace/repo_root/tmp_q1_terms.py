from pathlib import Path
text=Path('sources/beigene_management/2026_q1_10q.txt').read_text(encoding='utf-8')
for term in ['Total revenues','Revenue Total revenue','Net income','Net product revenue consisted','BRUKINSA','Income from operations','cash flows from operating activities','Cash, cash equivalents']:
 idx=text.lower().find(term.lower())
 print('\n===',term,idx,'===')
 if idx!=-1: print(text[idx:idx+2200].replace('\n',' '))

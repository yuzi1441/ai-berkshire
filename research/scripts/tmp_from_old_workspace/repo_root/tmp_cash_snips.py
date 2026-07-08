from pathlib import Path
text=Path('sources/beigene_management/2025_10k.txt').read_text(encoding='utf-8')
for term in ['At December 31, 2025', 'cash equivalents and short-term investments', 'cash and cash equivalents totaled', 'net cash provided by operating activities', 'positive free cash flow', 'Cash Flows']:
 idx=text.lower().find(term.lower())
 print('\n',term,idx)
 if idx!=-1: print(text[max(0,idx-300):idx+1500].replace('\n',' '))

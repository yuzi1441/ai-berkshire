from pathlib import Path
text=Path('sources/beigene_management/2025_10k.txt').read_text(encoding='utf-8')
for term in ['Amgen Collaboration Agreement', 'Amgen Collaboration', 'In October 2019', '20.5%', 'Novartis', 'Tislelizumab Collaboration', 'Ociperlimab Collaboration', 'BMS Collaboration', 'acquired the China', 'Celgene']:
 idx=text.lower().find(term.lower())
 print('\n===',term,idx,'===')
 if idx!=-1: print(text[max(0,idx-500):idx+2500].replace('\n',' ')[:3000])

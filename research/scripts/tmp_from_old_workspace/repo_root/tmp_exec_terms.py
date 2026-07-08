from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
terms=['Aaron Rosenberg has served', 'Xiaobin Wu has served', 'Lai Wang has served', 'Xiaodong Wang has served', 'Executive Officers', 'Our executive officers']
for term in terms:
 idx=text.lower().find(term.lower())
 print('\n===',term,idx,'===')
 if idx!=-1: print(text[max(0,idx-500):idx+3000])

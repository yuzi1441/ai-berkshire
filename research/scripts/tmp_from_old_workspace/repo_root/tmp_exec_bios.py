from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
for name in ['Xiaobin Wu','Aaron Rosenberg','Lai Wang','Xiaodong Wang']:
 idx=text.find(name)
 print('\n===',name,idx,'===')
 print(text[max(0,idx-800):idx+2500])

from pathlib import Path
text=Path('sources/四方股份/annual2025.txt').read_text(encoding='utf-8').splitlines()
for start in [1147,1190,1200,1235,1260,1540,1570,1725,1810,2295,2380,310,350,390,420,450,600,680,720]:
    print('\n---',start,'---')
    for k in range(start, min(len(text)+1,start+55)):
        print(f'{k}: {text[k-1]}')

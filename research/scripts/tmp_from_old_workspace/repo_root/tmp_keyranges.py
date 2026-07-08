from pathlib import Path
text=Path('sources/四方股份/annual2025.txt').read_text(encoding='utf-8').splitlines()
for start in [902,940,968,1020,1038,1060,1192,1200,1250,1539,1570,1597,1634,1725,1730,1808,1812,1815,1839,1848,2295,2300,2310,2360,2380,2420,2440,684,690,720,526,540]:
    print('\n---',start,'---')
    for k in range(start, min(len(text)+1,start+45)):
        print(f'{k}: {text[k-1]}')

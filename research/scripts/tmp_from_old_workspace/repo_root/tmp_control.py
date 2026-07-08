from pathlib import Path
text=Path('sources/四方股份/annual2025.txt').read_text(encoding='utf-8').splitlines()
for start in [2401,2420,2440,2450,2460,2470,2480,2490,2500]:
 print('\n---',start,'---')
 for k in range(start,min(len(text)+1,start+35)):
  print(f'{k}: {text[k-1]}')

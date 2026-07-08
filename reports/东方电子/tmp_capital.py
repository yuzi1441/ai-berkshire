from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
for s,e in [(3758,3798),(1900,1935),(2718,2768),(2720,2765),(7428,7448),(7560,7595),(7600,7635)]:
 print(f'\n===={s}-{e}====')
 for i in range(s,e+1):
  if i<=len(text): print(f'{i}: {text[i-1]}')

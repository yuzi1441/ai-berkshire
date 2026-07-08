from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
for s,e in [(2350,2380),(6740,6898),(7890,7900),(8428,8450),(1894,1918),(4208,4248)]:
 print(f'\n===={s}-{e}====')
 for i in range(s,e+1):
  if i<=len(text): print(f'{i}: {text[i-1]}')

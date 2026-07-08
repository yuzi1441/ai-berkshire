from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
for s,e in [(20,30),(2395,2438),(2690,2774),(3000,3025),(3040,3095),(3148,3162),(3350,3364),(3728,3795),(4180,4210),(4590,4625),(5110,5140),(8590,8665),(8640,8720),(9580,9665)]:
 print(f'\n===={s}-{e}====')
 for i in range(s,e+1):
  if i<=len(text): print(f'{i}: {text[i-1]}')

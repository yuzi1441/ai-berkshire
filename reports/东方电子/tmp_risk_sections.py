from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
# print around lines 1418-1495 and around risk term occurrences
for s,e in [(1418,1495),(1450,1580),(1750,1845),(1845,1905),(9200,9340),(9550,9665),(9665,9745)]:
 print(f'\n===={s}-{e}====')
 for i in range(s,e+1):
  if i<=len(text): print(f'{i}: {text[i-1]}')

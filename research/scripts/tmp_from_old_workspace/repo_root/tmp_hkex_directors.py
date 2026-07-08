from pathlib import Path
text=Path('sources/四方股份/hkex_application_20260616.txt').read_text(encoding='utf-8').splitlines()
for start in [6260,6300,6330,6360,6380]:
 print('\n---',start,'---')
 for k in range(start,min(len(text)+1,start+50)):
  print(f'{k}: {text[k-1]}')

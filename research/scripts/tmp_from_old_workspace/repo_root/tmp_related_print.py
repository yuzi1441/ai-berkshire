from pathlib import Path
text=Path('sources/四方股份/related_invest_20260430.txt').read_text(encoding='utf-8').splitlines()
for i,l in enumerate(text,1):
    if l.strip(): print(f'{i}: {l}')

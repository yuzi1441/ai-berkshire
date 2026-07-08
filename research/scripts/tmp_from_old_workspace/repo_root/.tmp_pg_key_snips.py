from pathlib import Path
text=Path('sources/平高电气/2025_annual.pdf.txt').read_text(encoding='utf-8')
for start in [6900, 10400, 15800, 16600, 17400, 18500, 39800, 41000, 129000, 136000, 145000, 151000]:
    print('\n---',start,'---')
    print(text[start:start+2200].replace('\n',' | '))

from pathlib import Path
lines=Path('sources/601126_2025AR.pdf.txt').read_text(encoding='utf-8').splitlines()
for a,b in [(4910,4968),(4870,4915),(580,620),(1006,1055),(977,1006)]:
    print(f'\n--- {a}-{b} ---')
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

from pathlib import Path
lines=Path('sources/601126_2025AR.pdf.txt').read_text(encoding='utf-8').splitlines()
for a,b in [(150,200),(2915,2945),(2990,3035),(7200,7220)]:
    print(f'\n--- {a}-{b} ---')
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

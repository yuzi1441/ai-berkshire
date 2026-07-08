from pathlib import Path
lines=Path('sources/601126_2025AR.pdf.txt').read_text(encoding='utf-8').splitlines()
for a,b in [(4950,5006),(5107,5125),(7710,7750),(7980,8020),(8110,8180),(8180,8265),(630,686),(930,1006)]:
    print(f'\n--- {a}-{b} ---')
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

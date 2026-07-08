from pathlib import Path
lines=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8').splitlines()
for a,b in [(2310,2390)]:
    for i in range(a-1,min(b,len(lines))): print(f'L{i+1}: {lines[i]}')

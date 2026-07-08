from pathlib import Path
lines=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8').splitlines()
for a,b in [(1277,1288),(1345,1367),(1980,1990),(2060,2065),(2310,2390),(2399,2455),(4905,4915),(8208,8215)]:
    print(f'\n===== L{a}-{b} =====')
    for i in range(a-1,min(b,len(lines))): print(f'L{i+1}: {lines[i]}')

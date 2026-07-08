from pathlib import Path
lines=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8').splitlines()
ranges=[(145,165),(375,435),(490,545),(1088,1165),(1350,1370),(1370,1545),(1540,1585),(1588,1635),(1830,1855),(1940,1990),(2030,2095),(2140,2235),(2300,2345),(2600,2620),(2730,2745),(3008,3018),(3070,3080)]
for a,b in ranges:
    print(f'\n===== L{a}-{b} =====')
    for i in range(a-1,min(b,len(lines))): print(f'L{i+1}: {lines[i]}')

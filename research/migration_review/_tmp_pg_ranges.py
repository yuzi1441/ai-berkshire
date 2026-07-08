from pathlib import Path
lines=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8').splitlines()
# print ranges around given line numbers (1-index)
ranges=[(90,130),(340,470),(1085,1110),(1220,1370),(1370,1585),(1585,1640),(1830,1860),(1940,1990),(2000,2105),(2160,2235),(2270,2335),(2420,2480),(2650,2740),(2800,2860),(2960,2995),(3210,3245)]
for a,b in ranges:
    print(f'\n===== L{a}-{b} =====')
    for i in range(a-1,min(b,len(lines))):
        print(f'L{i+1}: {lines[i]}')

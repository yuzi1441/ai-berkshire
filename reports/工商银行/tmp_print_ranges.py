from pathlib import Path
lines=Path('extracted_pages.txt').read_text(encoding='utf-8').splitlines()
for start,end in [(100,170),(3000,3260),(2440,2550),(2320,2420),(2580,2680),(1500,1700),(1760,1900),(2020,2140)]:
    print(f'\n### LINES {start}-{end}')
    for i in range(start-1, min(end, len(lines))):
        print(f'{i+1}: {lines[i]}')
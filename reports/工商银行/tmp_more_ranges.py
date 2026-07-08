from pathlib import Path
lines=Path('extracted_pages.txt').read_text(encoding='utf-8').splitlines()
for start,end in [(2860,3165),(3198,3255),(2490,2600),(3650,3740),(3740,3840),(3840,3920),(3920,3990),(1680,1840),(2140,2260),(2560,2680)]:
    print(f'\n### LINES {start}-{end}')
    for i in range(start-1, min(end, len(lines))):
        print(f'{i+1}: {lines[i]}')
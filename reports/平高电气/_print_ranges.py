from pathlib import Path
s=Path('_annual_key_pages_utf8.txt').read_text(encoding='utf-8-sig')
lines=s.splitlines()
for start,end in [(250,310),(360,430),(460,545),(560,660),(680,780),(2320,2380),(2428,2480),(2530,2600),(2650,2775),(2775,2860)]:
    print(f'\n--- lines {start}-{end} ---')
    for i in range(start-1, min(end,len(lines))):
        print(f'{i+1}: {lines[i]}')

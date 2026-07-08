from pathlib import Path
s=Path('四方股份2025annual_text.txt').read_text(encoding='utf-8')
for start in [318,330,340,350,407,430,455,930,950,977,986,1000]:
    print('\n---',start,'---')
    lines=s.splitlines()
    for i in range(start-1, min(start+35, len(lines))): print(f'{i+1}: {lines[i]}')

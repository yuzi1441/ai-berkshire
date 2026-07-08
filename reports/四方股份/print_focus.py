from pathlib import Path
s=Path('四方股份2025annual_text.txt').read_text(encoding='utf-8')
lines=s.splitlines()
for start,end in [(350,380),(407,475),(930,972),(977,1006),(1017,1042)]:
    print('\n---',start,end,'---')
    for i in range(start-1, min(end, len(lines))): print(f'{i+1}: {lines[i]}')

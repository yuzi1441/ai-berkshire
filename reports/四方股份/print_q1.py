from pathlib import Path
lines=Path('四方股份2026Q1_text.txt').read_text(encoding='utf-8').splitlines()
for start,end in [(1,90),(321,380),(380,450),(520,610)]:
    print('\n---',start,end,'---')
    for i in range(start-1, min(end,len(lines))): print(f'{i+1}: {lines[i]}')

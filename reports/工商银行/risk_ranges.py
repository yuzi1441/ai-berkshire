from pathlib import Path
lines=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for a,b,title in [(1488,1535,'risk intro and five class'),(1535,1655,'npl by business and industry'),(1655,1705,'overdue restructured'),(2240,2315,'note industry and overdue')]:
    print('\n###',title)
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

from pathlib import Path
lines=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for a,b,title in [(1530,1598,'risk fields and biz npl'),(1598,1665,'industry npl'),(1665,1698,'overdue')]:
    print('\n###',title)
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

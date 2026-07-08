from pathlib import Path
lines=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for a,b,title in [(274,350,'loan detail'),(350,470,'quality'),(470,590,'overdue and risk')]:
    print('\n###',title)
    for i in range(a-1,min(b,len(lines))): print(f'{i+1}: {lines[i]}')

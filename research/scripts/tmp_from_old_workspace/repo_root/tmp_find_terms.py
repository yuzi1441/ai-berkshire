from pathlib import Path
text=Path('sources/beigene_management/2026_proxy.txt').read_text(encoding='utf-8')
# find all security ownership headers after 200k
for term in ['Security Ownership', '5% shareholders', 'beneficial owners', 'beneficial ownership', 'Principal Shareholders', 'Ownership of Shares']:
    print('\n',term)
    start=0
    found=0
    while True:
        idx=text.lower().find(term.lower(), start)
        if idx==-1: break
        print(idx, text[idx:idx+100].replace('\n',' '))
        found+=1; start=idx+1
        if found>20: break

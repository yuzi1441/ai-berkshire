from pathlib import Path
for file in ['q1_text.txt']:
    txt=Path(file).read_text(encoding='utf-8')
    for pg in range(6,12):
        marker=f'---PAGE {pg}---'
        pos=txt.find(marker)
        pos2=txt.find(f'---PAGE {pg+1}---',pos+1)
        print('\n====',marker,'====')
        print(txt[pos: pos2 if pos2!=-1 else len(txt)])

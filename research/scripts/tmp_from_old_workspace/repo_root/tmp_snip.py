from pathlib import Path
text=Path('sources/四方股份/annual2025.txt').read_text(encoding='utf-8').splitlines()
for i,line in enumerate(text,1):
    if '现任及报告期内离任董事和高级管理人员持股变动及薪酬情况' in line:
        # find previous page marker
        prev=[(j,text[j-1]) for j in range(max(1,i-30),i) if text[j-1].startswith('--- PAGE')]
        print('hit line',i,'prev',prev[-1] if prev else None)
        for k in range(i, min(len(text),i+70)):
            print(f'{k}: {text[k-1]}')
        break

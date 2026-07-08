from pathlib import Path
text=Path('sources/annual_key_pages.txt').read_text(encoding='utf-8')
for pg in [13,14,15,18,19,20,23,24,25,27,28,32,33,46,47,49]:
    marker=f'===== PAGE {pg} ====='
    idx=text.find(marker)
    if idx>=0:
        end=text.find('===== PAGE', idx+10)
        snip=text[idx:end if end>idx else idx+5000]
        print('\n'+'='*20+' PAGE '+str(pg)+' '+'='*20)
        print(snip[:4500])
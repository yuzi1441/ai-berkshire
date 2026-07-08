from pathlib import Path
text=Path('sources/annual_pages_utf8.txt').read_text(encoding='utf-8')
for pg in [18,19,20,23,24,25,27,28,32,33,46,47,49]:
    marker=f'===== PAGE {pg} ====='
    idx=text.find(marker); end=text.find('===== PAGE', idx+1)
    print('\n'+'#'*8, pg)
    print(text[idx:end if end>0 else idx+3500][:4000])
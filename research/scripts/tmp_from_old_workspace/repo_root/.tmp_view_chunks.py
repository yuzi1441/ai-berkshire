from pathlib import Path
text=Path('sources/长江电力/cypc_2025_annual.pdf.txt').read_text(encoding='utf-8')
for start in [16000,16800,20000,22000,24000,25000,40000,7200,3000,11800,12400]:
    print('\n===== IDX',start,'=====')
    print(text[start:start+2500].replace('\n',' | '))

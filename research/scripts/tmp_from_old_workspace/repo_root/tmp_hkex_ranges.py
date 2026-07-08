from pathlib import Path
text=Path('sources/四方股份/hkex_application_20260616.txt').read_text(encoding='utf-8').splitlines()
for start in [3100,3130,3260,3400,4060,4110,4460,4670,4770,4788,5400,5780,6400,6500]:
    print('\n---HKEX',start,'---')
    for k in range(start, min(len(text)+1,start+55)):
        print(f'{k}: {text[k-1]}')

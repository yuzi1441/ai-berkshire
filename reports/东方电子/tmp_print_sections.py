from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
sections=[(119,145),(1148,1220),(1248,1360),(1378,1420),(2390,2435),(2768,2828),(2860,2895),(3008,3160),(3308,3370),(3364,3639),(3639,3790),(3870,3985),(3990,4050),(4180,4210),(4590,4625),(5100,5145),(5750,5825),(7420,7445),(8520,8615),(9580,9665)]
for s,e in sections:
    print(f'\n===== lines {s}-{e} =====')
    for i in range(s,e+1):
        if i<=len(text): print(f'{i}: {text[i-1]}')

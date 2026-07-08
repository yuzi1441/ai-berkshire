from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
for s,e in [(260,430),(438,470),(2380,2445),(2710,2775),(3868,4050),(4010,4050),(7420,7445),(10180,10250),(8520,8615),(5750,5825),(5720,5760),(9550,9665)]:
    print(f'\n===== {s}-{e} =====')
    for i in range(s,e+1):
        if i<=len(text): print(f'{i}: {text[i-1]}')

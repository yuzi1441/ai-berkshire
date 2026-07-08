from pathlib import Path
text=Path('sources/2025_annual.txt').read_text(encoding='utf-8').splitlines()
sections=[(75,130),(215,430),(1280,1460),(1460,1535),(2380,2445),(2760,2865),(3000,3165),(3260,3335),(3840,3895),(3960,4140),(8520,8615),(9270,9335),(9580,9665),(10180,10250)]
out=[]
for s,e in sections:
    out.append(f'\n===== lines {s}-{e} =====')
    for i in range(s,e+1):
        if 1<=i<=len(text): out.append(f'{i}: {text[i-1]}')
Path('sources/key_sections_utf8.txt').write_text('\n'.join(out),encoding='utf-8')
print('wrote sources/key_sections_utf8.txt')

from pathlib import Path
s=Path('_annual_full_text.txt').read_text(encoding='utf-8')
lines=s.splitlines()
ranges=[(130,170),(740,785),(1708,1755),(4640,4810),(5198,5245),(6130,6365),(6540,6575),(1065,1120)]
out=[]
for start,end in ranges:
    out.append(f'--- lines {start}-{end} ---')
    for i in range(start-1,min(end,len(lines))):
        out.append(f'{i+1}: {lines[i]}')
Path('_financial_ranges.txt').write_text('\n'.join(out), encoding='utf-8')
print('ok', len(lines))

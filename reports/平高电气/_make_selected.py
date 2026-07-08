from pathlib import Path
s=Path('_annual_key_pages_utf8.txt').read_text(encoding='utf-8-sig')
lines=s.splitlines()
ranges=[(360,430),(430,545),(545,660),(680,780),(2320,2380),(2428,2480),(2530,2600),(2650,2775)]
out=[]
for start,end in ranges:
    out.append(f'--- lines {start}-{end} ---')
    for i in range(start-1, min(end,len(lines))):
        out.append(f'{i+1}: {lines[i]}')
Path('_selected_ranges_utf8.txt').write_text('\n'.join(out), encoding='utf-8')
print(Path('_selected_ranges_utf8.txt').resolve(), Path('_selected_ranges_utf8.txt').stat().st_size)

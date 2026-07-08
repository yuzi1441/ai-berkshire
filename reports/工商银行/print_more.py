from pathlib import Path
text=Path('icbc_2025_annual_A_extract.txt').read_text(encoding='utf-8').splitlines()
for start,end in [(780,910),(1120,1220),(1230,1325),(1324,1390),(1460,1546)]:
    print(f'\n--- lines {start}-{end} ---')
    for i in range(start-1,min(end,len(text))):
        print(f'{i+1}: {text[i]}')

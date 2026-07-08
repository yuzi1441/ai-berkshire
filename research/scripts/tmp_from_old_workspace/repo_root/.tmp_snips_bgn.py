from pathlib import Path
import re, json
for file in ['sources/sec/2025_fy_press.html.txt','sources/sec/2026_q1_press.html.txt','sources/sec/2025_10k.html.txt','sources/sec/2026_q1_10q.html.txt']:
    text=Path(file).read_text(encoding='utf-8')
    print('\n====',file)
    for pat in ['BRUKINSA: Global sales totaled','Product Revenue', 'TEVIMBRA', 'Total revenue', 'Cash, cash equivalents', 'free cash flow', '2025', '2024', '2023']:
        for m in re.finditer(re.escape(pat),text,re.I):
            print('\n--',pat,'at',m.start(),'--')
            print(text[max(0,m.start()-600):m.start()+1600])
            break
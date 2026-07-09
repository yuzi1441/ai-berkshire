from pathlib import Path
s=Path('data/600420/tencent_quote_20260708.txt').read_text(encoding='utf-8')
inside=s.split('=\"',1)[1].rstrip('\";')
parts=inside.split('~')
for i,p in enumerate(parts):
    if p:
        print(i, p)

from pathlib import Path
import re
files=list(Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\cninfo_recent').rglob('*.pdf'))
for p in sorted(files):
    m=re.match(r'(\d{13})_', p.name)
    date=''
    if m:
        import datetime
        date=datetime.datetime.utcfromtimestamp(int(m.group(1))/1000).strftime('%Y-%m-%d')
    print(date, p.name[m.end():] if m else p.name, p.stat().st_size)

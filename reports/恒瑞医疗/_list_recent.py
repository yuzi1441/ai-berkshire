from pathlib import Path
import datetime
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\恒瑞医疗\source_pdfs\cninfo_recent')
for p in sorted(base.rglob('*.pdf')):
    ts=p.parent.name
    try:
        date=datetime.datetime.utcfromtimestamp(int(ts)/1000).strftime('%Y-%m-%d')
    except Exception: date=''
    print(date, p.name, p.stat().st_size)

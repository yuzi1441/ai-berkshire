from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\工商银行')
for f in base.glob('工商银行-earnings-2026Q1-*.md'):
    print('---', f.name, f.stat().st_size)
    try:
        txt=f.read_text(encoding='utf-8')
        print(txt[:500].replace('\n',' ') )
    except Exception as e: print('ERR', e)
from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\联影医疗')
for p in sorted(base.iterdir(), key=lambda x:x.stat().st_mtime, reverse=True)[:10]:
    print(f'{p.name}\t{p.stat().st_size}\t{p.stat().st_mtime}')

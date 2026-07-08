from pathlib import Path
p=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\长江电力\industry-researcher_长江电力_水电电力行业分析_2026-07-07.md')
text=p.read_text(encoding='utf-8')
print(text[:6000])

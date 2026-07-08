from pathlib import Path
p=Path(r'C:\Users\whatn\.codex\skills\management-deep-dive\SKILL.md')
text=p.read_text(encoding='utf-8-sig')
print(len(text))
print(text)
from pathlib import Path
text=Path('sources/mindray/mindray-2026-q1.txt').read_text(encoding='utf-8')
idx=text.find('分产线来看')
print(idx)
print(text[idx:idx+3500])

from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
idx=text.find('前十名股东持股情况')
print(idx)
print(text[idx:idx+5000])

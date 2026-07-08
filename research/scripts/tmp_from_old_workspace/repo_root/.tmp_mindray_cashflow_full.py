from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
idx=text.find('合并现金流量表')
while idx!=-1 and idx<190000: idx=text.find('合并现金流量表', idx+1)
print(idx)
print(text[idx:idx+5000])

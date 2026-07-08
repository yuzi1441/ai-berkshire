from pathlib import Path
text=Path('sources/联影医疗/2026Q1.pdf.txt').read_text(encoding='utf-8')
print(text[:12000])

from pathlib import Path
lines=Path('annual_selected_pages.txt').read_text(encoding='utf-8').splitlines()
for i in range(1588-1,1630): print(f'{i+1}: {lines[i]}')

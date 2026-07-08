from pathlib import Path
lines=Path('四方股份2025annual_text.txt').read_text(encoding='utf-8').splitlines()
for i in range(900-1, 972): print(f'{i+1}: {lines[i]}')

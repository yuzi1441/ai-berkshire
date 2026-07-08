from pathlib import Path
p=Path(r'C:\Users\whatn\.codex\memories\MEMORY.md')
lines=p.read_text(encoding='utf-8-sig').splitlines()
for a,b in [(24,34),(50,58),(465,500)]:
 print(f'--- {a}-{b} ---')
 for i in range(a,b+1):
  print(f'{i}: {lines[i-1]}')

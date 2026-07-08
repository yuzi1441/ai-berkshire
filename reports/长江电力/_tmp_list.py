from pathlib import Path
for p in Path('.').glob('__extract*'):
 print(p.name)

from pathlib import Path
for p in Path('source_docs/pgdq').glob('*'):
    print(p, p.stat().st_size)

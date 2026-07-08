from pathlib import Path
import json
# append IR evidence to bundle md
bundle=Path('sources/pgdq/evidence_bundle.md')
lines=Path('source_docs/pgdq/ir_2025_2026q1_20260424.txt').read_text(encoding='utf-8').splitlines()
sel='\n'.join(f'L{i}: {lines[i-1]}' for i in range(1,min(len(lines),120)+1))
with bundle.open('a',encoding='utf-8') as f:
    f.write('\n## 业绩说明会问答\n来源：`source_docs/pgdq/ir_2025_2026q1_20260424.txt` 行 1-120\n\n```text\n'+sel+'\n```\n')
print(bundle.stat().st_size)

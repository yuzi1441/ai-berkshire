from pathlib import Path
import re, json
annual=Path('source_docs/pgdq/pg_2025_annual.txt').read_text(encoding='utf-8')
q1=Path('source_docs/pgdq/pg_2026_q1.txt').read_text(encoding='utf-8')
# Extract exact slices by line ranges for evidence bundle
items=[]
def add(file,label,a,b):
    lines=Path(file).read_text(encoding='utf-8').splitlines()
    items.append({'label':label,'file':file,'lines':f'{a}-{b}','text':'\n'.join(f'L{i}: {lines[i-1]}' for i in range(a,min(b,len(lines))+1))})
for args in [
('source_docs/pgdq/pg_2025_annual.txt','2025主要财务指标',145,163),
('source_docs/pgdq/pg_2025_annual.txt','2025经营回顾与研发成果',380,421),
('source_docs/pgdq/pg_2025_annual.txt','2026经营计划',1096,1136),
('source_docs/pgdq/pg_2025_annual.txt','高管名单薪酬',1373,1401),
('source_docs/pgdq/pg_2025_annual.txt','高管履历',1410,1483),
('source_docs/pgdq/pg_2025_annual.txt','任职与兼职',1490,1539),
('source_docs/pgdq/pg_2025_annual.txt','薪酬机制',1539,1558),
('source_docs/pgdq/pg_2025_annual.txt','董事会出席',1594,1631),
('source_docs/pgdq/pg_2025_annual.txt','股权激励员工持股',1835,1853),
('source_docs/pgdq/pg_2025_annual.txt','承诺事项',1943,1985),
('source_docs/pgdq/pg_2025_annual.txt','股权结构控股股东',2140,2235),
('source_docs/pgdq/pg_2026_q1.txt','2026Q1财务和股东',23,31),
('source_docs/pgdq/pg_2026_q1.txt','2026Q1前十大股东',83,148),
('source_docs/pgdq/2025_profit_distribution.txt','利润分配',11,32),
('source_docs/pgdq/2025_profit_distribution.txt','中期分红计划',71,88),
('source_docs/pgdq/2025_dividend_implementation.txt','权益分派实施',11,25),
('source_docs/pgdq/board_secretary_change.txt','董秘变更',10,47),
('source_docs/pgdq/board_2026_04_11.txt','董事会表决',14,110),
]: add(*args)
Path('sources/pgdq/evidence_bundle.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
md=[]
for it in items:
    md.append(f"## {it['label']}\n来源：`{it['file']}` 行 {it['lines']}\n\n```text\n{it['text']}\n```\n")
Path('sources/pgdq/evidence_bundle.md').write_text('\n'.join(md),encoding='utf-8')
print('items',len(items), Path('sources/pgdq/evidence_bundle.md').stat().st_size)

from pathlib import Path
s=Path('_q1_full_text.txt').read_text(encoding='utf-8')
lines=s.splitlines()
for i,l in enumerate(lines, start=1):
    if any(p in l for p in ['营业收入','经营活动产生的现金流量净额','中国电气装备','前10名股东','总资产','应收账款','存货','合同资产','货币资金']):
        print(f'{i}: {l}')

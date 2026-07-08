from pathlib import Path
for year in [2022,2023,2024,2025]:
    p=Path(f'source_docs/pgdq/pg_{year}_annual.txt') if year<2025 else Path('source_docs/pgdq/pg_2025_annual.txt')
    lines=p.read_text(encoding='utf-8').splitlines()
    hits=[]
    for i,l in enumerate(lines,1):
        if '预计实现营业收入' in l or ('预计实现' in l and '营业收入' in l) or ('经营计划' in l and i<1200):
            hits.append(i)
    print('\n===',year,'hits',hits[:10])
    for h in hits[:5]:
        for j in range(max(1,h-3), min(len(lines),h+5)+1):
            print(f'L{j}: {lines[j-1]}')
        print('---')

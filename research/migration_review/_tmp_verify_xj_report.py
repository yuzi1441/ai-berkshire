from pathlib import Path
p=Path('reports/许继电气/许继电气研究报告-20260707.md')
text=p.read_text(encoding='utf-8')
checks=['许继电气（000400.SZ）研究报告','AI 研究偏见自觉','第八步：最终决策与行动清单','21.11 元','2026Q1','合理偏上价格']
print('path', p.resolve())
print('chars', len(text), 'bytes', p.stat().st_size)
for c in checks:
    print(c, c in text)

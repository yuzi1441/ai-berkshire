from pathlib import Path
p=Path('中国神华研究报告-20260707.md')
s=p.read_text(encoding='utf-8')
s=s.replace('| 2026Q1 年化 EPS | 1.97 元 | 0.53 × 4 / 新股本近似 |','| 2026Q1 年化摊薄 EPS | 1.97 元 | 106.67 亿元 × 4 / 216.8943 亿股 |')
s=s.replace('| 2026Q1 年化 PE | 21.3x | 41.91 / 1.97 |','| 2026Q1 年化摊薄 PE | 21.3x | 41.91 / 1.97 |')
s=s.replace('- `financial_rigor.py verify-valuation`：PE 17.18x、PB 1.89x、股息率 5.39%（该工具调用使用 2.26 元股息示例；正式报告按 2025 实际中期+末期 2.01 元/股重算为 4.80%）。','- `financial_rigor.py verify-valuation`：PE 17.18x、PB 1.89x、股息率 4.80%（按 2025 中期 0.98 元/股 + 末期 1.03 元/股，合计 2.01 元/股）。')
p.write_text(s,encoding='utf-8')
print('updated', p.resolve(), p.stat().st_size)

from pathlib import Path
p=Path('reports/四方股份/四方股份投资研究报告-20260707.md')
s=p.read_text(encoding='utf-8')
s=s.replace('2026-07-06 16:14:48，收盘价 60.96 元，总股本约 8.331055 亿股，总市值约 507.86 亿元。', '2026-07-06 16:14:48，收盘价 60.96 元；总股本约 8.331055 亿股；总市值约 507.86 亿元。')
s=s.replace('3. AIDC/SST 业务是否已有可披露订单、交付、毛利率和客户验证？', '3. AIDC / SST（Solid State Transformer，固态变压器）业务是否已有可披露订单、交付、毛利率和客户验证？')
p.write_text(s,encoding='utf-8')
print(p.resolve(), p.stat().st_size)

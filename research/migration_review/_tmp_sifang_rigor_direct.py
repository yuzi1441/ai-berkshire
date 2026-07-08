from tools import financial_rigor as fr
cases=[
('2025 revenue RMB hundred million', {'SSE annual':81.9331011395,'HKEX application proof':81.93310,'AkShare-Eastmoney':81.9331011395}, '亿元', 1.0),
('2025 net profit attributable RMB hundred million', {'SSE annual':8.2897042218,'HKEX application proof IFRS profit':8.28943,'AkShare-Eastmoney':8.2897042218}, '亿元', 1.0),
('2025 operating cashflow RMB hundred million', {'SSE annual':12.2465646311,'HKEX application proof':12.24656,'AkShare-Eastmoney per-share-derived':12.2465646311}, '亿元', 1.0),
('2026Q1 revenue RMB hundred million', {'SSE Q1':21.1737919197,'AkShare-Eastmoney':21.1737919197}, '亿元', 1.0),
('share count shares', {'Tencent quote total shares':833105500,'SSE Q1 implied from holder pct':833016087}, '股', 1.0),
]
for field, values, unit, tol in cases:
 print('\n###', field)
 fr.cross_validate(field, values, unit=unit, tolerance_pct=tol)

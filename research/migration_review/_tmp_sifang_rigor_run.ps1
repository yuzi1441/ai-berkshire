$env:PYTHONIOENCODING='utf-8'
python tools\financial_rigor.py cross-validate --field '2025 revenue RMB hundred million' --values '{"SSE annual":81.9331011395,"HKEX application proof":81.93310,"AkShare-Eastmoney":81.9331011395}' --unit '亿元'
python tools\financial_rigor.py cross-validate --field '2025 net profit attributable RMB hundred million' --values '{"SSE annual":8.2897042218,"HKEX application proof IFRS profit":8.28943,"AkShare-Eastmoney":8.2897042218}' --unit '亿元'
python tools\financial_rigor.py cross-validate --field '2025 operating cashflow RMB hundred million' --values '{"SSE annual":12.2465646311,"HKEX application proof":12.24656,"AkShare-Eastmoney per-share-derived":12.2465646311}' --unit '亿元'
python tools\financial_rigor.py cross-validate --field '2026Q1 revenue RMB hundred million' --values '{"SSE Q1":21.1737919197,"AkShare-Eastmoney":21.1737919197}' --unit '亿元'
python tools\financial_rigor.py cross-validate --field 'share count shares' --values '{"Tencent quote total shares":833105500,"SSE Q1 implied from holder pct":833016087}' --unit '股' --tolerance 0.02

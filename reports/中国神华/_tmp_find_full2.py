from pathlib import Path
text=Path('_tmp_annual2025_full.txt').read_text(encoding='utf-8')
for kw in ['===== PAGE 163','现金及现金等价物余额','购建固定资产','货币资金 96,772','短期借款 409','长期借款 28,268','应付债券','现金及现金等价物净减少额','已分派','末期股息','中期股息','股息','拟派发','2.26']:
 print('\n###',kw)
 i=text.find(kw)
 print(i)
 if i!=-1: print(text[i-1000:i+2500])

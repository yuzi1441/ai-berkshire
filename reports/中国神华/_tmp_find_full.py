from pathlib import Path
text=Path('_tmp_annual2025_full.txt').read_text(encoding='utf-8')
for kw in ['合并现金流量表','合并资产负债表','合并利润表','货币资金','短期借款','长期借款','应付债券','分部收入小计','利润总额 46,597','资本开支计划','已分配的末期股息','每股分派现金红利','股利']:
    print('\n###',kw)
    i=text.find(kw)
    print(i)
    if i!=-1: print(text[i-800:i+2800])

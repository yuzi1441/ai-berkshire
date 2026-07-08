from pathlib import Path
text=Path('_annual_full.txt').read_text(encoding='utf-8')
for kw in ['合并现金流量表','经营活动产生的现金流量净额','购建固定资产、无形资产和其他长期资产支付的现金']:
 print(kw, text.rfind(kw))
idx=text.rfind('合并现金流量表')
print(text[idx:idx+8000])

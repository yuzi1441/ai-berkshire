from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
for term in ['购建固定资产、无形资产和其他长期资产支付的现金','投资活动现金流出小计']:
 idx=text.find(term)
 print('\n',term,idx)
 print(text[idx-500:idx+1200])

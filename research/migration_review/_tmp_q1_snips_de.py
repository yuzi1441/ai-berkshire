from pathlib import Path
text=(Path('sources')/'东方电子'/'东方电子-2026年一季度报告.txt').read_text(encoding='utf-8')
for term in ['主要会计数据和财务指标','合并资产负债表','合并利润表','合并现金流量表']:
    idx=text.find(term)
    print('\n---',term,'idx',idx,'---')
    print(text[idx:idx+3000])
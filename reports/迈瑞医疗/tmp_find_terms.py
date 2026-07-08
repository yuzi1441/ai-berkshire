from pathlib import Path
text=Path('ar_text.txt').read_text(encoding='utf-8')
for term in ['1、合并资产负债表','2、合并利润表','3、合并现金流量表','合并资产负债表','合并利润表','合并现金流量表']:
    print(term, [m.start() for m in __import__('re').finditer(term,text)][:10])

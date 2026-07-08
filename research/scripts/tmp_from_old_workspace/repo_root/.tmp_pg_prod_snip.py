from pathlib import Path
text=Path('sources/平高电气/2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['主营业务分产品情况','高压板块','配网板块','运维检修及', '主营业务分地区情况', '销售前五名客户']:
    i=text.find(term)
    print('\n###',term, i)
    if i>=0: print(text[i:i+1800].replace('\n',' | '))

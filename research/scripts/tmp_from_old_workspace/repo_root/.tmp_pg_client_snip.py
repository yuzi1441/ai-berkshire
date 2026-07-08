from pathlib import Path
text=Path('sources/平高电气/2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['客户集中', '前五名客户', '前5名客户', '销售额', '供应商']:
    i=text.find(term)
    print('\n###',term, i)
    if i>=0: print(text[max(0,i-600):i+1600].replace('\n',' | '))

from pathlib import Path
text=Path('sources/平高电气/2025_annual.pdf.txt').read_text(encoding='utf-8')
for term in ['购建固定资产', '取得投资收益收到的现金', '投资活动产生的现金流量净额', '分配股利', '现金分红', '每10股派发现金红利']:
    print('\n###',term)
    i=text.find(term)
    print(i)
    print(text[max(0,i-500):i+1200].replace('\n',' | ') if i>=0 else '')

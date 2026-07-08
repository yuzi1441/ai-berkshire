import pathlib,re
text=pathlib.Path('sources/长江电力/annual2025.pdf.txt').read_text(encoding='utf-8')
for term in ['购建固定资产、无形资产和其他长期资产支付的现金','分配股利、利润或偿付利息支付的现金','取得投资收益收到的现金','吸收投资收到的现金','偿还债务支付的现金','取得借款收到的现金','筹资活动产生的现金流量净额','经营活动产生的现金流量净额']:
    print('\n###',term)
    for m in re.finditer(re.escape(term),text):
        s=max(0,m.start()-200); e=min(len(text),m.end()+300)
        print(text[s:e].replace('\n',' '))
        print('---')

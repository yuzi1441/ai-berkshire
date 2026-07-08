from pathlib import Path
base=Path('sources/beigene_management')
patterns=['John V. Oyler','Xiaodong Wang','Aaron Rosenberg','executive officers','Summary Compensation Table','beneficially owned','no controlling shareholders','Dual Primary','Net product revenues','BRUKINSA','Global Powerhouse','profitability','operating leverage','cash flows from operating activities','related person transactions','We have not identified','Sustainability','employee']
for fname in ['2025_10k.txt','2026_q1_10q.txt','2026_proxy.txt','2024_10k.txt','2023_10k.txt']:
    text=(base/fname).read_text(encoding='utf-8')
    print('\n====',fname,'====')
    low=text.lower()
    for pat in patterns:
        idx=low.find(pat.lower())
        if idx!=-1:
            sn=text[max(0,idx-500):idx+1200].replace('\n',' ')
            print('\n--',pat,'--')
            print(sn[:1600])

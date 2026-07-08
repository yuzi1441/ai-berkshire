from pathlib import Path
base=Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\reports\迈瑞医疗')
texts={
 'q1': (base/'sources'/'mindray_2026_q1.txt').read_text(encoding='utf-8'),
 'annual': (base/'sources'/'mindray_2025_annual.txt').read_text(encoding='utf-8'),
}
for name,text in texts.items():
    print('\n====',name,'chars',len(text),'====')
    pats=['一、主要财务数据','二、股东信息','合并利润表','合并现金流量表','研发投入','境外','体外诊断类产品','生命信息与支持类产品','医学影像类产品','新兴业务类产品','未来发展','回购','分红','商誉','应收账款','存货','医疗新基建','反腐','集采','国际市场','国内市场']
    for pat in pats:
        idx=text.find(pat)
        if idx>=0:
            snip=text[max(0,idx-200):idx+1200].replace('\n',' ')
            print('\n---',pat,'@',idx,'---')
            print(snip[:1400])

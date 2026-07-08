from pathlib import Path
text=Path('sources/联影医疗/2025年报.pdf.txt').read_text(encoding='utf-8')
patterns=['风险因素','国际贸易摩擦','贸易摩擦','海外监管','关税','应收账款回收风险','存货跌价','核心竞争力风险','产品销售收入确认','预期信用损失','其他收益','长期应收款','合同负债']
for pat in patterns:
    print('\n###',pat)
    start=0; n=0
    while True:
        i=text.find(pat,start)
        if i<0: break
        print('@',i,'\n',text[max(0,i-450):i+1500])
        start=i+len(pat); n+=1
        if n>=3: break

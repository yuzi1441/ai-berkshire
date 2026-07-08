from pathlib import Path
files=[Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf.txt'),Path('sources/联影医疗/lianying_q1_20260429_1225233744.pdf.txt')]
patterns=['营业收入','归属于上市公司股东的净利润','研发投入','主营业务分行业','主营业务分产品','主营业务分地区','境外','海外','市场占有率','装机','总资产','经营活动产生的现金流量净额','货币资金','应收账款','存货','毛利率','董事长','薛敏','张强','实际控制人','股本']
for f in files:
    print('\nFILE',f)
    text=f.read_text(encoding='utf-8',errors='ignore')
    for pat in patterns:
        idx=text.find(pat)
        if idx!=-1:
            print('\n###',pat,'at',idx)
            print(text[max(0,idx-500):idx+1500])

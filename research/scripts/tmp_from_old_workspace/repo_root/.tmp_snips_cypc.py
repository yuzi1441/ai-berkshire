from pathlib import Path
text=Path('sources/长江电力/cypc_2025_annual.pdf.txt').read_text(encoding='utf-8')
patterns=['电力行业','水电行业','市场化交易','上网电量','平均上网电价','售电收入','境内所属六座','发电量 3071.94','装机容量 7179.5','主营业务分行业','主营业务分产品','分行业','资产收购','分红','承诺','不低于','利润分配','资产负债率','投资收益','财务费用','营业成本','毛利率','长江经济带','雅砻江','国投电力','川投能源','华能水电','现金分红']
for pat in patterns:
    print('\n###',pat)
    start=0; count=0
    while count<4:
        i=text.find(pat,start)
        if i<0: break
        print('IDX',i, text[i-300:i+600].replace('\n',' | '))
        start=i+len(pat); count+=1

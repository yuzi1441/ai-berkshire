from bs4 import BeautifulSoup
from pathlib import Path
for name in ['annual','q1']:
    text=Path(f'.tmp_sina_{name}.html').read_text(encoding='utf-8')
    soup=BeautifulSoup(text,'html.parser')
    plain=soup.get_text('\n')
    print('\n===== ', name, '====')
    kws=['主要会计数据和财务指标','主要会计数据','营业收入','归属于上市公司股东的净利润','归属于上市公司股东的扣除非经常性损益的净利润','经营活动产生的现金流量净额','基本每股收益','加权平均净资产收益率','报告期主要业务或产品简介','公司主要产品','营业收入构成','占公司营业收入或营业利润10%以上的行业','境外','研发投入','现金分红','应收账款','存货','合同负债','营业总收入','营业利润','净利润']
    for kw in kws:
        hits=[m.start() for m in __import__('re').finditer(kw, plain)]
        print(kw, hits[:8])
        for idx in hits[:2]:
            print('--- snippet', idx, '---')
            print(plain[idx:idx+1200])

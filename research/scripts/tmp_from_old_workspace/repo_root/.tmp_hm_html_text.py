from pathlib import Path
from bs4 import BeautifulSoup
import re
base=Path('reports/华明装备/sources')
for htmlfn in ['sina_2025AR_11972985.html','sina_2026Q1_12201904.html','sina_2024AR_10862534.html']:
    html=(base/htmlfn).read_text(encoding='utf-8',errors='ignore')
    soup=BeautifulSoup(html,'lxml')
    # remove scripts styles
    for tag in soup(['script','style']): tag.decompose()
    text=soup.get_text('\n')
    text=re.sub(r'\n{2,}','\n',text)
    out=base/(htmlfn+'.text.txt')
    out.write_text(text,encoding='utf-8')
    print('\n====',htmlfn,'len',len(text),'====')
    for kw in ['主要会计数据和财务指标','营业收入构成','主营业务分析','分行业','分产品','研发投入','经营活动产生的现金流量净额','前10名股东','实际控制人','控股股东','股利分配','核心竞争力','境外','分接开关','未来发展']:
        idx=text.find(kw)
        print('KW',kw,idx)
        if idx!=-1:
            print(text[idx:idx+1500])
            print('---')

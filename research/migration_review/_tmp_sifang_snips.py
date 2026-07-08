from pathlib import Path
import re, sys
sys.stdout.reconfigure(encoding='utf-8')
text=Path('sources/sifang/relevant_extract.md').read_text(encoding='utf-8')
for pat in ['报告期内公司所处行业情况','报告期内公司从事的业务情况','主营业务分产品','营业收入和营业成本','前五名客户','前五名供应商','研发投入','主要研发项目','按業務線劃分','市場份額','中國繼電保護市場','變電站自動化','五大客戶','我們的供應商','董事及高級管理層','控股股東','新型電力系統市場','核心技術','中國新型電力系統市場','2025年至2030年']:
    print('\n===== PAT',pat,'=====')
    n=0
    for m in re.finditer(re.escape(pat), text):
        print('\n--- at',m.start(),'---')
        print(text[max(0,m.start()-700):m.start()+2500].replace('\n',' ')[:3200])
        n+=1
        if n>=3: break
    if n==0: print('none')

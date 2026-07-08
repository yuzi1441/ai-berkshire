from pathlib import Path
text=Path('sources/联影医疗/lianying_annual_20260429_1225233728.pdf.pypdf.txt').read_text(encoding='utf-8')
for start,end in [(93000,101000),(101000,111000),(111000,121000),(121000,132000),(132000,145000),(145000,160000),(160000,180000),(180000,200000),(200000,230000),(230000,260000),(260000,300000),(300000,350000)]:
    sub=text[start:end]
    print('\n=== range',start,end,'pageapprox',sub[:50].replace('\n',' ') ,'===')
    for pat in ['营业收入','分产品','分地区','研发投入','市场占有率','竞争','主要竞争','专利','客户','供应商','实际控制人','风险因素','政府补助','前五名客户','前五名供应商','受限','境外收入','行业']:
        if pat in sub:
            print('has',pat,'at',start+sub.find(pat))

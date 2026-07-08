from pathlib import Path
text=Path('sources/mindray/mindray-2025-annual.txt').read_text(encoding='utf-8')
terms=['三、主营业务分析','营业收入构成','占营业收入比重','分产品','生命信息与支持','体外诊断','医学影像','境外地区','研发投入','现金流','经营活动产生的现金流量净额','公司主要销售客户情况','前五名客户','前五名供应商','货币资金','资产总计','负债合计','归属于上市公司股东的净资产']
for term in terms:
    print('\n===',term,'===')
    idx=text.find(term)
    print('idx',idx)
    if idx!=-1:
        print(text[idx:idx+2500])

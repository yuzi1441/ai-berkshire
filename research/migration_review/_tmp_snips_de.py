from pathlib import Path
base=Path('sources')/'东方电子'
for name in ['东方电子-2025年年度报告.txt','东方电子-2026年一季度报告.txt']:
    text=(base/name).read_text(encoding='utf-8')
    print('\n###',name)
    for term in ['主要会计数据和财务指标','分行业','分产品','主营业务','研发投入','经营活动产生的现金流量净额','合并资产负债表','合并利润表','合并现金流量表','公司未来发展的展望','公司可能面对的风险']:
        idx=text.find(term)
        if idx!=-1:
            print(f'\n--- {term} ---')
            print(text[idx:idx+3500])
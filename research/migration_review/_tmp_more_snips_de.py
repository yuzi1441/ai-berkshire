from pathlib import Path
text=(Path('sources')/'东方电子'/'东方电子-2025年年度报告.txt').read_text(encoding='utf-8')
for term in ['研发人员数量','研发投入金额','研发投入资本化','主要控股参股公司分析','南方电网数字电网集团信息通信科技有限公司','公司未来发展的展望','公司可能面对的风险','技术研发风险','市场竞争风险','海外发展的政治风险']:
    idx=text.find(term)
    print('\n---',term,idx,'---')
    if idx!=-1: print(text[idx:idx+4500])
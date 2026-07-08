from pathlib import Path
text=(Path('sources')/'东方电子'/'东方电子-2025年年度报告.txt').read_text(encoding='utf-8')
terms=['115','中标额','累计中标','配网区域联合采购','AI+','海颐软件','威思顿','五年以上','5年以上','合同履约成本','南网数字','国家电网固定资产投资','十五五','4万亿元']
for term in terms:
    idx=text.find(term)
    print('\n---',term,idx,'---')
    if idx!=-1: print(text[max(0,idx-600):idx+1800])
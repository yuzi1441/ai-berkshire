from pathlib import Path
import re, json
base=Path('sources/cninfo_hmzb')
for fn in ['20260227_2025年年度报告.txt','20250411_2024年年度报告.txt','20240411_2023年年度报告.txt','20230412_2022年年度报告.txt','20220601_2021年年度报告（修订稿）.txt']:
    text=(base/fn).read_text(encoding='utf-8',errors='ignore')
    print('\n==',fn)
    for pat in ['营业收入（元）','归属于上市公司股东的净利润（元）','经营活动产生的现金流量净额（元）','基本每股收益（元/股）','2025 年','2024 年','2023 年','2022 年','2021 年']:
        pos=text.find(pat)
        if pos!=-1: print('PAT',pat,'POS',pos, text[pos:pos+900].replace('\n',' '))
    # around main financial table
    pos=text.find('主要会计数据和财务指标')
    print('mainpos',pos, text[pos:pos+3000].replace('\n',' ')[:3000])
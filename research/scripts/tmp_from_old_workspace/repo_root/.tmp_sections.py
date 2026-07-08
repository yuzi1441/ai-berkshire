from pathlib import Path
import re
base=Path('sources/cninfo_hmzb')
text=(base/'20260227_2025年年度报告.txt').read_text(encoding='utf-8',errors='ignore')
for pat in ['四、董事、监事、高级管理人员报酬情况','五、公司员工情况','三、任职情况','公司现任董事、监事、高级管理人员专业背景','2、公司控股股东情况','3、公司实际控制人及其一致行动人','前十名股东持股情况','十七、公司子公司重大事项','主营业务分析','十一、公司未来发展的展望','2025 年整体经营情况','报告期内公司从事的主要业务']:
    pos=text.find(pat)
    print('\nPAT',pat,'POS',pos)
    if pos!=-1:
        print(text[pos:pos+5000].replace('\n',' ')[:5000])
from pathlib import Path
import re, sys
text=Path('sources/002028/text/2025AR.txt').read_text(encoding='utf-8')
patterns=['货币资金','短期借款','长期借款','有息负债','合同负债','存货','应收账款','资本支出','购建固定资产','在建工程','研发费用','现金及现金等价物余额','分产品','业务收入','公司主营业务','输配电设备','海外']
for pat in patterns:
    print('\n###',pat)
    for m in list(re.finditer(pat,text))[:5]:
        s=max(0,m.start()-400); e=min(len(text),m.start()+1000)
        print(text[s:e].replace('\n',' ')[:1400])
        print('---')

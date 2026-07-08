from pathlib import Path
import re
for f in ['Announce20260429_5.txt','2025AnnualReportA.txt']:
    txt = Path(f).read_text(encoding='utf-8')
    print('\n###', f)
    pats = ['净利润','不良贷款率','拨备覆盖率','资本充足率','核心一级资本','净利息收益率','房地产','地方政府','逾期','重组','关注类','信用减值','承诺','资产质量','风险','管理层讨论','战略','普惠','绿色金融','现金流']
    for pat in pats:
        m = re.search(pat, txt)
        if m:
            s=max(0,m.start()-200); e=min(len(txt),m.end()+300)
            print('\n--',pat,'--')
            print(txt[s:e].replace('\n',' ')[:700])

from pathlib import Path
text = Path('2025AnnualReportA.txt').read_text(encoding='utf-8')
patterns = ['不良贷款余额','不良贷款率','拨备覆盖率','关注类贷款','逾期贷款','重组贷款','房地产业','地方政府','地方债','政府融资平台','净利息收益率','资本充足率','核心一级资本充足率','信用减值损失','阶段三','第一阶段','第二阶段','第三阶段','贷款五级分类','延期还本付息','减值准备','房地产贷款','地方政府债券','金融投资']
for pat in patterns:
    print('\n###', pat)
    starts=[]
    pos=0
    while True:
        i=text.find(pat,pos)
        if i==-1: break
        starts.append(i); pos=i+1
        if len(starts)>=5: break
    print('count first', len(starts), starts[:5])
    for i in starts[:2]:
        s=max(0,i-700); e=min(len(text),i+1200)
        print('---snippet---')
        print(text[s:e].replace('\n',' ')[:2000])

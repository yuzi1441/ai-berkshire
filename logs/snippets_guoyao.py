from pathlib import Path
files=['annual_2025','q1_2026','related_2026','profit_2025','finance_company_risk','impairment_2026jan','central_procurement_2026feb','board_2025_change','consistency_20260701']
patterns=['主要会计数据','营业收入','原料药及医药中间体板块','制剂板块','行业格局','带量采购','风险','股东总数','前十名股东','控股股东','实际控制人','董事、监事和高级管理人员','关联交易','应收账款','商誉','现金流量表','经营活动产生的现金流量净额','利润分配','国药集团财务有限公司','应收款项融资','减值准备','拟中选','完成董事会换届','董事长','总裁','环保','安全生产','合规']
base=Path('research/sources/国药现代')
for f in files:
    text=(base/(f+'.txt')).read_text(encoding='utf-8')
    print('\n====',f,'====')
    for pat in patterns:
        idx=text.find(pat)
        if idx!=-1:
            s=max(0,idx-300); e=min(len(text),idx+900)
            snippet=text[s:e].replace('\n',' ')
            print(f'-- {pat}: {snippet[:1200]}')

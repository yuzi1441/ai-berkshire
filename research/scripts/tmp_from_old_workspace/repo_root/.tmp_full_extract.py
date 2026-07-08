from pathlib import Path
import pdfplumber, re
annual=Path('sources/思源电气/siyuan_2025_annual_sina.pdf')
q1=Path('sources/思源电气/siyuan_2026_q1_sina.pdf')
for label,p in [('annual',annual),('q1',q1)]:
    with pdfplumber.open(p) as pdf:
        text='\n'.join((page.extract_text(x_tolerance=1,y_tolerance=3) or '') for page in pdf.pages)
    Path(f'sources/思源电气/{label}_text.txt').write_text(text,encoding='utf-8')
    print(label, len(text))
    for kw in ['营业收入构成','占公司营业收入或营业利润10%以上的行业','分产品','分地区','境外','主营业务分析','研发投入','现金流','资产及负债状况分析','应收账款','存货','合同资产','合同负债','利润分配预案','前10名股东持股情况','董事、监事和高级管理人员情况','公司产品主要包括','公司主要从事']:
        hits=[m.start() for m in re.finditer(re.escape(kw), text)]
        print('\nKW',kw,hits[:10])
        for idx in hits[:2]:
            sn=text[idx:idx+2500]
            print(sn.replace('\n','\n'))
            print('---')

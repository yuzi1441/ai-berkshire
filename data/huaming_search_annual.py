from pathlib import Path
text=Path('data/huaming_002270/pdf_text/2025AR_1224986242.pdf.txt').read_text('utf-8')
patterns=['第二节 公司简介和主要财务指标','主要会计数据和财务指标','经营情况讨论与分析','管理层讨论与分析','主营业务分析','营业收入构成','分行业','分产品','分地区','现金流','资产及负债状况','未来发展的展望','关联交易','承诺事项','或有事项','股份支付','客户和供应商','前五名客户','前五名供应商','研发投入']
for pat in patterns:
    print('\n###',pat)
    idx=0; count=0
    while True:
        idx=text.find(pat, idx)
        if idx<0 or count>=5: break
        print('@',idx, text[idx:idx+800].replace('\n',' | '))
        idx+=len(pat); count+=1

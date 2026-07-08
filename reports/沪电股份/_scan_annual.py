from pathlib import Path
text=Path('source_pdfs/hudian_2025_annual.pdf.extract.txt').read_text(encoding='utf-8')
keywords=['行业分类','产品分类','印制电路板','毛利率','营业成本','主营业务分析','货币资金','短期借款','长期借款','资产负债率','前五名客户','研发人员','研发投入金额','现金及现金等价物','购建固定资产','投资支付的现金','存货','应收账款','客户销售额','通讯通信设备板','汽车板','数据中心']
for kw in keywords:
    print('\n===== KW',kw,'=====')
    start=0; c=0
    while True:
        idx=text.find(kw,start)
        if idx==-1 or c>=3: break
        print('idx',idx)
        print(text[max(0,idx-800):idx+1600])
        print('---')
        start=idx+len(kw); c+=1

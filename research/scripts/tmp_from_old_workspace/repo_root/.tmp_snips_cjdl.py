import re, pathlib, json
text=pathlib.Path('sources/长江电力/annual2025.pdf.txt').read_text(encoding='utf-8')
terms=['公司以大型水电运营','管理层讨论与分析','主要会计数据','主要财务指标','主营业务分行业情况','资产负债率','有息负债','发电量','售电量','装机容量','现金分红','利润分配','中国长江三峡集团有限公司','董事长','总经理','公司治理','重大事项','同业竞争','关联交易','投资收益','资本开支','固定资产','在建工程','货币资金','短期借款','长期借款','应付债券','归属于上市公司股东的所有者权益']
for term in terms:
    print('\n###',term)
    for m in list(re.finditer(re.escape(term), text))[:5]:
        s=max(0,m.start()-250); e=min(len(text),m.end()+500)
        print(text[s:e].replace('\n',' ')[:1000])
        print('---')

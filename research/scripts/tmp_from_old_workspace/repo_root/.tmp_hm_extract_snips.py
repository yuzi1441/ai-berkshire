import pdfplumber, pathlib, re, json
src=pathlib.Path('sources/huaming')
files=['1224986242_2025年年度报告.PDF','1225181771_2026年一季度报告.PDF','1223055875_2024年年度报告.PDF','1219567826_2023年年度报告.PDF','1216380949_2022年年度报告.PDF','1224992209_关于回购公司股份方案实施完毕暨回购实施结果的公告.PDF','1222674027_关于回购公司股份方案的公告.PDF','1221697938_关于诉讼事项的公告.PDF','1205034020_关于对深交所_关于对华明电力装备股份有限公司2017年年报的问询函_回复的公告.PDF','1203624500_关于对深圳证券交易所2016年年报问询函的回复公告.PDF']
keywords=['实际控制人','控股股东','董事长','总经理','管理层','股权激励','限制性股票','分红','利润分配','回购','应收账款','存货','商誉','客户集中','前五名客户','境外','汇率','原材料','诉讼','处罚','问询','业绩承诺','重大资产重组','减持','关联交易','研发','质量','安全','海外','外销','承诺']
for fn in files:
    p=src/fn
    if not p.exists(): continue
    print('\n### FILE',fn)
    with pdfplumber.open(p) as pdf:
        for i,page in enumerate(pdf.pages):
            try: text=page.extract_text() or ''
            except Exception: text=''
            if any(k in text for k in keywords):
                # print focused snippets around keywords
                shown=[]
                compact=' '.join(text.split())
                for k in keywords:
                    idx=compact.find(k)
                    if idx!=-1:
                        start=max(0,idx-180); end=min(len(compact), idx+500)
                        sn=compact[start:end]
                        if sn not in shown:
                            print(f'-- page {i+1} kw {k}: {sn[:900]}')
                            shown.append(sn)
                        break

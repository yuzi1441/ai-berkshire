import pdfplumber, pathlib, re, json, sys
src=pathlib.Path('sources/huaming')
out=[]
patterns=['主要会计数据','营业收入','归属于上市公司股东','经营活动产生的现金流量净额','前五名客户','应收账款','存货','商誉','境外','国外','外销','汇率','原材料','风险','实际控制人','控股股东','前十名股东','董事、监事、高级管理人员','现金分红','利润分配','回购','关联交易','产品质量','安全','诉讼','处罚','股权激励','承诺','业绩承诺','薪酬','募集资金','减持']
files=list(src.glob('*2025年年度报告.PDF'))+list(src.glob('*2026年一季度报告.PDF'))+list(src.glob('*2024年年度报告.PDF'))+list(src.glob('*2023年年度报告.PDF'))+list(src.glob('*2022年年度报告.PDF'))+list(src.glob('*回购公司股份方案实施完毕*.PDF'))+list(src.glob('*诉讼事项*.PDF'))+list(src.glob('*问询函*回复*.PDF'))
for p in files:
    with pdfplumber.open(p) as pdf:
        for i,page in enumerate(pdf.pages):
            text=page.extract_text(x_tolerance=1,y_tolerance=3) or ''
            if any(pt in text for pt in patterns):
                compact=' '.join(text.split())
                hits=[pt for pt in patterns if pt in compact]
                for pt in hits[:3]:
                    idx=compact.find(pt)
                    out.append({'file':p.name,'page':i+1,'kw':pt,'snippet':compact[max(0,idx-300):min(len(compact),idx+1000)]})
(pathlib.Path('sources/huaming/extract_snippets.json')).write_text(json.dumps(out,ensure_ascii=False,indent=2),encoding='utf-8')
print(len(out))

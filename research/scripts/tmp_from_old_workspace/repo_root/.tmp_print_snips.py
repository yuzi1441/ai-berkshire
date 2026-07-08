import json
d=json.load(open('sources/huaming/extract_snippets.json',encoding='utf-8'))
keys=['实际控制人','前十名股东','前五名客户','应收账款','存货','商誉','境外','汇率','原材料','产品质量','诉讼','处罚','现金分红','回购','股权激励','承诺','业绩承诺','关联交易','减持','风险']
for k in keys:
    print('\n##',k)
    n=0
    for x in d:
        if x['kw']==k or k in x['snippet']:
            print(f"{x['file']} p{x['page']} {x['kw']}: {x['snippet'][:700]}")
            n+=1
            if n>=5: break

import json
D=json.load(open('sources/huaming/extract_snippets.json',encoding='utf-8'))
keys=['前五名客户','应收账款','存货','商誉','境外','汇率','原材料','诉讼','处罚','现金分红','回购','业绩承诺','减持']
for k in keys:
    print('\n@@@',k)
    n=0
    for x in D:
        if k in x['snippet']:
            sn=x['snippet'].replace('\n',' ')
            print(f"{x['file']} p{x['page']} kw={x['kw']}\n{sn[:1200]}\n")
            n+=1
            if n>=8: break

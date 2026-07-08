import requests, json, pathlib
codes={'600312':'平高电气','002028':'思源电气','601179':'中国西电','000400':'许继电气','600406':'国电南瑞'}
s=requests.Session(); s.trust_env=False
rows=[]
for code,name in codes.items():
    prefix='sh' if code.startswith('6') else 'sz'
    r=s.get(f'https://qt.gtimg.cn/q={prefix}{code}',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
    body=r.content.decode('gbk','ignore').split('="',1)[1].rsplit('"',1)[0]
    f=body.split('~')
    rows.append({'代码':code,'名称':f[1],'价格':f[3],'PE_TTM':f[39],'总市值亿元':f[44],'流通市值亿元':f[45],'PB':f[46],'日期时间':f[30]})
print(json.dumps(rows,ensure_ascii=False,indent=2))
path=pathlib.Path('reports/平高电气/同行腾讯行情估值_20260706.json'); path.write_text(json.dumps(rows,ensure_ascii=False,indent=2),encoding='utf-8')

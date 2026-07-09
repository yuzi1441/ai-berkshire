import requests, re, json, pathlib
r=requests.get('https://qt.gtimg.cn/q=sh600372',timeout=15)
s=r.content.decode('gbk','ignore')
print(s)
val=s.split('="',1)[1].rsplit('"',1)[0].split('~')
for i,x in enumerate(val): print(i,x)
pathlib.Path('data/600372').mkdir(parents=True,exist_ok=True)
json.dump({'raw':s,'fields':val},open('data/600372/tencent_quote_20260709.json','w',encoding='utf-8'),ensure_ascii=False,indent=2)
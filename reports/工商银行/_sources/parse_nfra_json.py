import requests,json
url='https://www.nfra.gov.cn/cn/static/data/DocInfo/SelectByDocId/data_docId=1260352.json'
r=requests.get(url); r.encoding='utf-8'
data=r.json()['data']
for k in ['docTitle','publishDate','docSource','documentNo','remark2']:
 print(k, data.get(k))
print('content?', data.keys())
for k,v in data.items():
 if isinstance(v,str) and ('工商' in v or '罚' in v or len(v)>100): print('\n',k, v[:2000])

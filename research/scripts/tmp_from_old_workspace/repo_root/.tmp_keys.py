import json
j=json.load(open('sources/beigene_companyfacts_20260706.json',encoding='utf-8'))
keys=[]
for tax,facts in j['facts'].items():
  for k,v in facts.items():
    if any(s in k.lower() for s in ['product','collaboration','license','royalt','revenue']): keys.append((tax,k, list(v['units'].keys())))
for x in keys: print(x)
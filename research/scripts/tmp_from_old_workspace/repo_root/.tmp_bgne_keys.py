import json
j=json.load(open('sources/beigene_companyfacts_20260706.json',encoding='utf-8'))
for tax in ['bgne','dei','us-gaap']:
 print('TAX',tax)
 facts=j['facts'].get(tax,{})
 for k,v in facts.items():
  if any(s in k.lower() for s in ['brukinsa','tevimbra','tislelizumab','xgeva','blincyto','kyprolis','pobevcy','productrevenue','revenue']):
   print(k, list(v['units'].keys())[:5])
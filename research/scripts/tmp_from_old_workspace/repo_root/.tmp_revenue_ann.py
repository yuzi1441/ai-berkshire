import json, re
j=json.load(open('sources/beigene_companyfacts_20260706.json',encoding='utf-8'))

def ann(c):
 arr=j['facts']['us-gaap'][c]['units']['USD']; res={}
 for x in arr:
  if x.get('form') in ('10-K','10-K/A') and x.get('fp')=='FY' and x.get('start')==x.get('end','')[:4]+'-01-01' and x.get('end','').endswith('12-31'):
   y=int(x['end'][:4])
   if y>=2020 and (y not in res or x['filed']>res[y]['filed']): res[y]=x
 return res
for c in ['RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueGoodsNet','LicenseAndServicesRevenue','Revenues','SalesRevenueGoodsGross']:
 print('\n',c)
 for y,x in sorted(ann(c).items()): print(y,x['val'],x['filed'],x['accn'])
import requests, json, os, re
from collections import defaultdict
headers={'User-Agent':'whatn research whatn@example.com','Accept-Encoding':'gzip, deflate'}
url='https://data.sec.gov/api/xbrl/companyfacts/CIK0001651308.json'
r=requests.get(url,headers=headers,timeout=30)
print(r.status_code, len(r.text))
path='sources/beigene_companyfacts_20260706.json'
os.makedirs('sources',exist_ok=True)
open(path,'w',encoding='utf-8').write(r.text)
data=r.json()
print(data['entityName'])
for tax in data['facts']:
    print('tax',tax, 'facts', len(data['facts'][tax]));
print('sample us-gaap keys relevant')
keys=[k for k in data['facts'].get('us-gaap',{}) if any(s.lower() in k.lower() for s in ['Revenue','Sales','NetIncome','Cash','Research','OperatingIncome','Assets','Liabilities','StockholdersEquity','EarningsPerShare','WeightedAverage'])]
for k in sorted(keys)[:200]: print(k)
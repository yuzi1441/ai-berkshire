import json, pathlib
j=json.loads(pathlib.Path('sources/live_data.json').read_text(encoding='utf-8'))
r=j['em_annual']['result']['data'][0]
for k in sorted(r.keys()):
    if any(s in k for s in ['CASH','NET','PROFIT','OPERATE','ASSET','LIAB','TOTAL','REVE','DEBT','ROE','BPS','EPS']):
        print(k, r[k])

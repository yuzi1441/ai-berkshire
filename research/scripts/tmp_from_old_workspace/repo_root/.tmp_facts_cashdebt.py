import json, pathlib
p=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\beigene_companyfacts_20260706.json')
d=json.loads(p.read_text(encoding='utf-8'))
facts=d['facts']['us-gaap']
for key in ['NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations','LongTermDebtCurrent','LongTermDebtNoncurrent']:
 print('\n##',key)
 if key in facts:
  for unit,arr in facts[key]['units'].items():
   for x in [y for y in arr if (y.get('fy') or 0)>=2025][-12:]: print(unit,x)

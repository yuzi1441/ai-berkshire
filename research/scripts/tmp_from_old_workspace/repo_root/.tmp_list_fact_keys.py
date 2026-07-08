import json, pathlib
p=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\beigene_companyfacts_20260706.json')
d=json.loads(p.read_text(encoding='utf-8'))
allfacts={}
for ns, fs in d['facts'].items():
    allfacts.update(fs)
patterns=['Cash','Marketable','Securities','Operating','Capital','PropertyPlant','Lease','Debt','Equity','Research','Development','ShareBased','Repurchase','Dividend']
for key in sorted(allfacts):
    if any(p.lower() in key.lower() for p in patterns):
        print(key)

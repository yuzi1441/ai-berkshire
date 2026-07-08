import json, pathlib
p=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\beigene_companyfacts_20260706.json')
d=json.loads(p.read_text(encoding='utf-8'))
facts=d['facts']['us-gaap']
keys=['CashAndCashEquivalentsAtCarryingValue','AvailableForSaleSecuritiesDebtSecuritiesCurrent','DebtSecuritiesAvailableForSaleExcludingAccruedInterestCurrent','EquitySecuritiesFvNi','Assets','Liabilities','StockholdersEquity','LongTermDebt','LongTermDebtCurrent','LongTermDebtNoncurrent','NetCashProvidedByUsedInOperatingActivities','PaymentsToAcquirePropertyPlantAndEquipment','ResearchAndDevelopmentExpense','OperatingIncomeLoss','ShareBasedCompensation']
for key in keys:
    if key not in facts: print('MISSING',key); continue
    print('\n##',key)
    for unit, arr in facts[key]['units'].items():
        filtered=[x for x in arr if (x.get('fy') or 0)>=2025]
        for x in filtered[-6:]: print(unit,x)

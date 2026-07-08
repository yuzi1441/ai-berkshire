import json, pathlib
p=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\beigene_companyfacts_20260706.json')
d=json.loads(p.read_text(encoding='utf-8'))
print(d.keys())
print(d.get('entityName'))
print(d.get('cik'))
facts=d['facts'].get('us-gaap',{})
for key in ['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','NetIncomeLoss','GrossProfit','Assets','Liabilities','StockholdersEquity','CashAndCashEquivalentsAtCarryingValue','NetCashProvidedByUsedInOperatingActivities','PaymentsToAcquirePropertyPlantAndEquipment','ResearchAndDevelopmentExpense','SellingGeneralAndAdministrativeExpense','WeightedAverageNumberOfDilutedSharesOutstanding','WeightedAverageNumberOfSharesOutstandingBasic','EarningsPerShareBasic','EarningsPerShareDiluted']:
    if key in facts:
        units=facts[key].get('units',{})
        print('\n',key, list(units.keys())[:5])
        arr=next(iter(units.values()))
        for x in arr[-8:]: print(x)

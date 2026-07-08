import json, pathlib, math
from collections import defaultdict
p=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire\sources\beigene_companyfacts_20260706.json')
d=json.loads(p.read_text(encoding='utf-8'))
facts=d['facts']['us-gaap']
keys=['RevenueFromContractWithCustomerExcludingAssessedTax','NetIncomeLoss','GrossProfit','Assets','Liabilities','StockholdersEquity','CashAndCashEquivalentsAtCarryingValue','MarketableSecuritiesCurrent','ShortTermInvestments','NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations','PaymentsToAcquirePropertyPlantAndEquipment','ResearchAndDevelopmentExpense','SellingGeneralAndAdministrativeExpense','OperatingIncomeLoss','CostsAndExpenses','WeightedAverageNumberOfSharesOutstandingBasic','EarningsPerShareBasic','EarningsPerShareDiluted']
for key in keys:
    if key not in facts:
        continue
    print('\n##',key, list(facts[key]['units'].keys()))
    for unit, arr in facts[key]['units'].items():
        # filter latest 2022+ frames/fy
        chosen=[]
        for x in arr:
            if x.get('fy') and x['fy']>=2022:
                chosen.append(x)
        for x in chosen[-12:]:
            print(unit, x)

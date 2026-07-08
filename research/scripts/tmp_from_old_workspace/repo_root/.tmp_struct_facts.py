import json, datetime, re, os
from decimal import Decimal

data=json.load(open('sources/beigene_companyfacts_20260706.json',encoding='utf-8'))

def get_units(concept):
    c=data['facts'].get('us-gaap',{}).get(concept)
    if not c: return {}
    return c['units']

def annual(concept, unit='USD', years=range(2021,2026)):
    arr=get_units(concept).get(unit,[])
    res={}
    for x in arr:
        if x.get('form') in ('10-K','10-K/A') and x.get('fp')=='FY':
            end=x.get('end','')
            start=x.get('start')
            if re.match(r'\d{4}-12-31$',end or '') and start==f"{end[:4]}-01-01":
                y=int(end[:4])
                if y in years:
                    # prefer latest filing non-amend? latest filed
                    if y not in res or x.get('filed','')>res[y].get('filed',''):
                        res[y]=x
    return res

def instant(concept, dates, unit='USD'):
    arr=get_units(concept).get(unit,[])
    res={}
    for x in arr:
        end=x.get('end','')
        if end in dates and x.get('form') in ('10-K','10-Q','10-K/A','10-Q/A'):
            if end not in res or x.get('filed','')>res[end].get('filed',''):
                res[end]=x
    return res

concepts=['Revenues','SalesRevenueGoodsNet','LicenseAndServicesRevenue','CostOfRevenue','CostOfGoodsAndServicesSold','GrossProfit','ResearchAndDevelopmentExpense','SellingGeneralAndAdministrativeExpense','OperatingIncomeLoss','NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','PaymentsToAcquirePropertyPlantAndEquipment']
for c in concepts:
    print('\n',c)
    res=annual(c,'USD')
    for y,x in sorted(res.items()): print(y,x['val'],x['filed'],x['accn'])

print('\nINST')
for c in ['CashAndCashEquivalentsAtCarryingValue','ShortTermInvestments','AvailableForSaleSecuritiesDebtSecuritiesCurrent','Assets','Liabilities','StockholdersEquity','AccountsPayableAndAccruedLiabilitiesCurrent','LiabilitiesCurrent','AssetsCurrent']:
    print('\n',c)
    for d,x in sorted(instant(c,['2025-12-31','2026-03-31'],'USD').items()): print(d,x['val'],x['filed'])

print('\nEPS and shares')
for c,u in [('EarningsPerShareBasic','USD/shares'),('EarningsPerShareDiluted','USD/shares'),('WeightedAverageNumberOfSharesOutstandingBasic','shares'),('WeightedAverageNumberOfDilutedSharesOutstanding','shares')]:
    print('\n',c,u, get_units(c).keys())
    for y,x in sorted(annual(c,u).items()): print(y,x['val'],x['filed'])

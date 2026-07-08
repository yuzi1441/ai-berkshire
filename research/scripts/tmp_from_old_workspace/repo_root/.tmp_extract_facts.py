import json, datetime, os, re
from decimal import Decimal
path='sources/beigene_companyfacts_20260706.json'
data=json.load(open(path,encoding='utf-8'))

def facts(concept, unit='USD'):
    c=data['facts'].get('us-gaap',{}).get(concept)
    if not c:
        return []
    units=c['units']
    if unit not in units:
        # print(concept, units.keys())
        unit=next(iter(units))
    return units[unit]

def show(concept, unit='USD'):
    arr=facts(concept,unit)
    print('\n##',concept,unit,'n=',len(arr))
    # filter annual 10-K FY and quarter 10-Q recent
    for x in arr[-30:]:
        print({k:x.get(k) for k in ['fy','fp','form','filed','start','end','val','frame','accn']})

for c in ['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueGoodsNet','LicenseAndServicesRevenue','CostOfRevenue','CostOfGoodsAndServicesSold','ResearchAndDevelopmentExpense','SellingGeneralAndAdministrativeExpense','OperatingIncomeLoss','NetIncomeLoss','NetCashProvidedByUsedInOperatingActivities','PaymentsToAcquirePropertyPlantAndEquipment','CashAndCashEquivalentsAtCarryingValue','ShortTermInvestments','AvailableForSaleSecuritiesDebtSecuritiesCurrent','Assets','Liabilities','StockholdersEquity','EarningsPerShareBasic','WeightedAverageNumberOfSharesOutstandingBasic']:
    show(c)
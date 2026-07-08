import json, csv, re
from pathlib import Path

base=Path('data/sec_companyfacts_20260706')
quotes={}
for row in csv.DictReader(open('data/dc_electrical_cnbc_quotes_20260706.csv', encoding='utf-8-sig')):
    quotes[row['symbol']]=row
shares={'ETN':393_000_000,'VRT':382_000_000,'GEV':276_000_000,'POWL':12_100_000,'NVT':166_000_000,'HUBB':53_700_000,'PWR':151_000_000,'CEG':307_000_000,'VST':331_000_000,'TLN':50_000_000}
subsector={
 'ETN':'低压/中压配电、UPS、电气系统集成',
 'VRT':'数据中心电源/热管理/机柜基础设施',
 'GEV':'电网设备、变压器、电气化、燃机',
 'POWL':'定制化开关柜/配电系统/数据中心与油气',
 'NVT':'电气连接/机柜/热管理外壳',
 'HUBB':'公用事业和电气解决方案',
 'PWR':'电网工程/EPC/公用事业服务',
 'CEG':'核电/无碳电源',
 'VST':'发电资产/容量与PPA',
 'TLN':'核电+数据中心PPA弹性'
}

def latest_fact(facts, names, form_priority=('10-K','10-Q'), fy=None):
    us=facts.get('facts',{}).get('us-gaap',{})
    cand=[]
    for n in names:
        units=us.get(n,{}).get('units',{})
        for unit, arr in units.items():
            for x in arr:
                if x.get('form') in form_priority and 'val' in x:
                    if fy is not None and x.get('fy')!=fy: continue
                    # prefer annual for 10-K: fp FY; quarterly for 10-Q: fp Q*
                    cand.append((x.get('end',''), x.get('filed',''), x.get('form'), x.get('fp'), unit, x.get('val'), n, x.get('fy')))
    if not cand: return None
    # Prefer latest filed, then annual FY for 10-K duration facts with larger frame
    cand.sort(key=lambda t:(t[0] or '', t[1] or ''))
    return cand[-1]

def annual_fact(facts, names):
    us=facts.get('facts',{}).get('us-gaap',{})
    cand=[]
    for n in names:
        for unit, arr in us.get(n,{}).get('units',{}).items():
            for x in arr:
                if x.get('form')=='10-K' and x.get('fp')=='FY' and 'val' in x:
                    cand.append((x.get('fy'), x.get('end'), x.get('filed'), unit, x.get('val'), n))
    if not cand: return None
    cand.sort(key=lambda t:(t[0] or 0, t[2] or ''))
    return cand[-1]

rows=[]
for f in base.glob('*.json'):
    sym=f.name.split('_')[0]
    facts=json.loads(f.read_text(encoding='utf-8'))
    rev=annual_fact(facts, ['Revenues','RevenueFromContractWithCustomerExcludingAssessedTax','SalesRevenueNet'])
    ni=annual_fact(facts, ['NetIncomeLoss','ProfitLoss'])
    assets=annual_fact(facts, ['Assets'])
    liab=annual_fact(facts, ['Liabilities'])
    equity=annual_fact(facts, ['StockholdersEquity','StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest'])
    ocf=annual_fact(facts, ['NetCashProvidedByUsedInOperatingActivities','NetCashProvidedByUsedInOperatingActivitiesContinuingOperations'])
    price=float(quotes.get(sym,{}).get('last') or 0)
    sh=shares.get(sym)
    mcap=price*sh/1e9 if price and sh else ''
    net=ni[4] if ni else None
    pe=(price*sh/net) if price and sh and net and net>0 else ''
    debt_ratio=(liab[4]/assets[4]*100) if liab and assets and assets[4] else ''
    roe=(net/equity[4]*100) if net and equity and equity[4] else ''
    rows.append({
        'symbol':sym,'name':quotes.get(sym,{}).get('name',''),'subsector':subsector.get(sym,''),'price':price,
        'mcap_est_usd_b':round(mcap,2) if mcap!='' else '', 'shares_est_m':round(sh/1e6,1) if sh else '',
        'pe_est':round(pe,1) if pe!='' else '', 'quote_date':quotes.get(sym,{}).get('timestamp',''),
        'revenue_usd_b':round(rev[4]/1e9,2) if rev else '', 'revenue_year':rev[0] if rev else '',
        'net_income_usd_b':round(net/1e9,2) if net else '', 'ocf_usd_b':round(ocf[4]/1e9,2) if ocf else '',
        'ocf_to_np':round(ocf[4]/net,2) if ocf and net and net else '',
        'roe_pct':round(roe,1) if roe!='' else '', 'debt_ratio_pct':round(debt_ratio,1) if debt_ratio!='' else '',
        'source_quote':'CNBC quote-html-webservice','source_fin':'SEC companyfacts 10-K latest annual',
        'confidence_note':'市值用CNBC价格×估算股本；精确股本需以最新10-Q封面复核'
    })
rows.sort(key=lambda r: {'ETN':0,'VRT':1,'GEV':2,'POWL':3,'NVT':4,'HUBB':5,'PWR':6,'CEG':7,'VST':8,'TLN':9}.get(r['symbol'],99))
path=Path('data/dc_electrical_us_candidates_20260706.csv')
with path.open('w', newline='', encoding='utf-8-sig') as fp:
    w=csv.DictWriter(fp, fieldnames=list(rows[0].keys())); w.writeheader(); w.writerows(rows)
print(path, len(rows))

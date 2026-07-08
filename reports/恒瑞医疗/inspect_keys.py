import json
obj=json.load(open('sources/eastmoney_600276_financials.json',encoding='utf-8'))
for typ in ['RPT_DMSK_FN_CASHFLOW','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_BALANCE','RPT_F10_FINANCE_MAINFINADATA']:
    print('\nTYPE',typ)
    data=obj[typ]
    r=next(x for x in data if x.get('REPORT_DATE','').startswith('2025-12-31'))
    for k,v in r.items():
        if any(s in k.upper() for s in ['CASH','FIX','CONSTRUCT','ASSET','CAPITAL','PURCHASE','PAY','OPERATE','REVE','PROFIT','COST','EXPENSE','R_D','R&D','LIABIL','EQUITY','MONETARY','INVENTORY','RESEARCH','DEVELOP']):
            print(k, v)
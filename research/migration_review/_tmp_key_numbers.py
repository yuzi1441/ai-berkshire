import json, re, os
raw=json.load(open('reports/工商银行/_tmp_eastmoney_raw.json',encoding='utf-8'))
main=raw['f10main']['result']['data']
profit=raw['profit']['result']['data']
for r in main[:20]:
 if '年报' in r.get('REPORT_DATE_NAME','') or '一季报' in r.get('REPORT_DATE_NAME',''):
  print(r['REPORT_DATE_NAME'], r['REPORT_DATE'][:10], {
   'revenue_bn': r.get('TOTALOPERATEREVE')/1e8 if r.get('TOTALOPERATEREVE') else None,
   'np_bn': r.get('PARENTNETPROFIT')/1e8 if r.get('PARENTNETPROFIT') else None,
   'eps':r.get('EPSJB'), 'bps':r.get('BPS'), 'roe':r.get('ROEJQ'),
   'deposits_bn': r.get('TOTALDEPOSITS')/1e8 if r.get('TOTALDEPOSITS') else None,
   'loans_bn': r.get('GROSSLOANS')/1e8 if r.get('GROSSLOANS') else None,
   'npl': r.get('NONPERLOAN'), 'npl_amt_bn': r.get('NON_PERFORMING_LOAN')/1e8 if r.get('NON_PERFORMING_LOAN') else None,
   'coverage': r.get('CAPITAL_PROVISIONS_SUM') or r.get('LOAN_PROVISION_RATIO') or r.get('RISK_COVERAGE'),
   'cet1':r.get('HXYJBCZL') or r.get('FIRST_ADEQUACY_RATIO'), 'car':r.get('NEWCAPITALADER'),
   'nim':r.get('NET_INTEREST_MARGIN'), 'spread':r.get('NET_INTEREST_SPREAD'),
   'total_assets_bn': r.get('TOTAL_ASSETS_PK')/1e8 if r.get('TOTAL_ASSETS_PK') else None,
   'shares': r.get('TOTAL_SHARE')
  })
print('\nKeys nonnull 2025:')
r=[x for x in main if x.get('REPORT_DATE_NAME')=='2025年报'][0]
for k,v in r.items():
 if v not in [None,''] and any(s in k for s in ['CAPITAL','LOAN','NON','RISK','DEPOSIT','ASSET','SHARE','INTEREST','MARGIN','ADEQUACY','ZCFZ','HXY','NEW']):
  print(k,v)
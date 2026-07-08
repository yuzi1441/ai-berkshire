import requests,json
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'}
for rn in ['RPT_DMSK_FN_CASHFLOW','RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_INCOME','RPT_F10_FINANCE_MAINFINADATA']:
 url=f'https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=REPORT_DATE&sortTypes=-1&pageSize=20&pageNumber=1&reportName={rn}&columns=ALL&filter=(SECURITY_CODE%3D%22002270%22)'
 data=s.get(url,headers=headers,timeout=20).json()['result']['data']
 print('\n---',rn,'---')
 for d in data:
  if d.get('REPORT_TYPE')=='年报' or str(d.get('REPORT_DATE','')).startswith(('2025-12-31','2024-12-31','2023-12-31','2022-12-31','2021-12-31')):
   keys=['REPORT_DATE','REPORT_TYPE','TOTAL_OPERATE_INCOME','PARENT_NETPROFIT','DEDUCT_PARENT_NETPROFIT','NETCASH_OPERATE','CONSTRUCT_LONG_ASSET','TOTAL_ASSETS','TOTAL_LIABILITIES','MONETARYFUNDS','SHORT_LOAN','LONG_LOAN','TOTAL_EQUITY','EPSJB','BPS','MGJYXJJE','TOTALOPERATEREVE','PARENTNETPROFIT','KCFJCXSYJLR','ROEJQ','ROEKCJQ','XSMLL','XSJLL','ZCFZL']
   print({k:d.get(k) for k in keys if k in d})
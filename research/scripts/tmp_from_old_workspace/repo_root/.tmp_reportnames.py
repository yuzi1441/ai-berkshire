import requests,json
s=requests.Session(); s.trust_env=False
names=['RPT_F10_FINANCE_MAINFINADATA','RPT_F10_FINANCE_GMAINFINADATA','RPT_F10_FINANCE_GMAINFINA','RPT_DMSK_FN_MAININDICATOR','RPT_DMSK_FN_INCOME','RPT_DMSK_FN_BALANCE','RPT_DMSK_FN_CASHFLOW']
for rn in names:
 url=f'https://datacenter-web.eastmoney.com/api/data/v1/get?sortColumns=REPORT_DATE&sortTypes=-1&pageSize=3&pageNumber=1&reportName={rn}&columns=ALL&filter=(SECURITY_CODE%3D%22002270%22)'
 r=s.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://data.eastmoney.com/'},timeout=20)
 j=r.json(); print(rn, j.get('success'), j.get('message'), 'has', bool((j.get('result') or {}).get('data')))
 if (j.get('result') or {}).get('data'):
  print(list(j['result']['data'][0].keys())[:30])
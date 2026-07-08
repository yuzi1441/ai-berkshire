import requests, json, pandas as pd, os, pathlib
url='https://datacenter.eastmoney.com/securities/api/data/v1/get?reportName=RPT_VALUEANALYSIS_DET&columns=ALL&filter=(SECURITY_CODE="600276")&pageNumber=1&pageSize=10&sortTypes=-1&sortColumns=TRADE_DATE'
s=requests.Session(); s.trust_env=False
r=s.get(url,timeout=20,headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
print(r.status_code, r.text[:300])
data=r.json()['result']['data']
pathlib.Path('data/hengrui').mkdir(exist_ok=True,parents=True)
pd.DataFrame(data).to_csv('data/hengrui/em_valuation_20260706.csv',index=False,encoding='utf-8-sig')
print(pd.DataFrame(data).head().to_string(index=False))

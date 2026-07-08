import requests, json
base='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SZ000400'}
for t in [0,1,2]:
 print('--- type',t)
 r=requests.get(base,params={'type':t,'code':'SZ000400'},headers=headers,timeout=20)
 print(r.status_code,r.headers.get('content-type'),r.text[:1000])
 open(f'tmp_zyzb_{t}.json','w',encoding='utf-8').write(r.text)
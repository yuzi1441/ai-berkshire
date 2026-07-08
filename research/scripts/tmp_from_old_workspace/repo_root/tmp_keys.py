import requests, json
url='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=1&code=SH600312'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SH600312'}
data=requests.get(url,headers=headers,timeout=20).json()['data']
print(len(data))
row=data[0]
print(row.keys())
for k,v in row.items():
    if any(s in k for s in ['TOTAL','OPERATE','NETPROFIT','ROE','GROSS','DEBT','BASIC','MG','BPS','EPS','CAPITAL','CASH','ASSIGN']):
        print(k, v)
print(json.dumps(data[:6],ensure_ascii=False)[:5000])
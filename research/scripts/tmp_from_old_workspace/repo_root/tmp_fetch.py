import requests, json
url='https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/ZYZBAjaxNew?type=1&code=SH600312'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://emweb.securities.eastmoney.com/PC_HSF10/NewFinanceAnalysis/Index?type=web&code=SH600312'}
r=requests.get(url,headers=headers,timeout=20)
print(r.status_code, r.url, r.text[:500])
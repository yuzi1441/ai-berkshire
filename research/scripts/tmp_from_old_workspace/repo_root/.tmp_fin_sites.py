import requests
for url in ['https://stockanalysis.com/stocks/onc/financials/','https://stockanalysis.com/stocks/onc/financials/cash-flow-statement/','https://stockanalysis.com/stocks/onc/financials/balance-sheet/','https://www.macrotrends.net/stocks/charts/ONC/beone-medicines/revenue']:
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
 print('\n',url,r.status_code,len(r.text),r.text[:200])
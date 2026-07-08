import requests, json, re
for sym in ['ONC','6160.HK','688235.SS']:
 url=f'https://query1.finance.yahoo.com/v7/finance/quote?symbols={sym}'
 r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=15)
 print('\n',sym,r.status_code,r.text[:1000])
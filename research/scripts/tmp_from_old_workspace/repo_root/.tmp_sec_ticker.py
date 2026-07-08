import requests, json, re
ua={'User-Agent':'research contact@example.com'}
for ticker in ['ONC','BGNE']:
    url=f'https://www.sec.gov/files/company_tickers.json'
print('fetch tickers')
r=requests.get('https://www.sec.gov/files/company_tickers.json',headers=ua,timeout=20)
print(r.status_code, r.text[:80])
data=r.json()
for k,v in data.items():
    if v['ticker'] in ['ONC','BGNE'] or 'BEONE' in v['title'].upper() or 'BEIGENE' in v['title'].upper():
        print(k,v)
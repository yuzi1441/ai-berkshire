import requests, json
headers={'User-Agent':'codex-research whatn@example.com'}
data=requests.get('https://data.sec.gov/submissions/CIK0001651308.json',headers=headers,timeout=20).json()
recent=data['filings']['recent']
print(len(recent['form']))
print(recent.keys())
for i in range(min(20,len(recent['form']))):
    print(i, repr(recent['filingDate'][i]), repr(recent['form'][i]), repr(recent['accessionNumber'][i]), repr(recent['primaryDocument'][i]), repr(recent['primaryDocDescription'][i]))

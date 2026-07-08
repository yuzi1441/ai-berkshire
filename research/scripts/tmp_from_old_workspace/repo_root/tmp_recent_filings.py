import requests
headers={'User-Agent':'codex-research whatn@example.com'}
data=requests.get('https://data.sec.gov/submissions/CIK0001651308.json',headers=headers,timeout=20).json()
recent=data['filings']['recent']
for i in range(0,140):
 if recent['filingDate'][i] >= '2026-02-01':
  print(i, recent['filingDate'][i], recent['form'][i], recent['accessionNumber'][i], recent['primaryDocument'][i], recent['primaryDocDescription'][i], recent['items'][i])

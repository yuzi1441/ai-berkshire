import requests, json
headers={'User-Agent':'whatn research whatn@example.com','Accept-Encoding':'gzip, deflate','Host':'data.sec.gov'}
data=requests.get('https://data.sec.gov/submissions/CIK0001651308.json',headers=headers,timeout=20).json()
recent=data['filings']['recent']
count=0
for i in range(len(recent['form'])):
    form=recent['form'][i]
    if form in ['10-K','10-Q','20-F','6-K','8-K','10-K/A','10-Q/A']:
        print(i, form, recent['filingDate'][i], recent['reportDate'][i], recent['accessionNumber'][i], recent['primaryDocument'][i], recent['primaryDocDescription'][i])
        count+=1
        if count>=80: break
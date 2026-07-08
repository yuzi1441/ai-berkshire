import requests, json, os, re
headers={'User-Agent':'whatn research whatn@example.com','Accept-Encoding':'gzip, deflate','Host':'data.sec.gov'}
cik='0001651308'
url=f'https://data.sec.gov/submissions/CIK{cik}.json'
r=requests.get(url,headers=headers,timeout=20)
print(r.status_code, r.text[:200])
data=r.json()
recent=data['filings']['recent']
for i,(form,acc,fd,rd,doc,desc) in enumerate(zip(recent['form'],recent['accessionNumber'],recent['filingDate'],recent['reportDate'],recent['primaryDocument'],recent['primaryDocDescription'])):
    if form in ['10-K','10-Q','20-F','6-K','8-K']:
        print(i, form, fd, rd, acc, doc, desc)
        if i>30: break
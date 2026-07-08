import urllib.request,json
cik='0001651308'; data=json.loads(urllib.request.urlopen(urllib.request.Request(f'https://data.sec.gov/submissions/CIK{cik}.json',headers={'User-Agent':'codex research contact@example.com'}),timeout=20).read())
r=data['filings']['recent']
for i,(date,form,acc,doc) in enumerate(zip(r['filingDate'],r['form'],r['accessionNumber'],r['primaryDocument'])):
    if form in ['10-Q','10-K','20-F','6-K','8-K']:
        print(i,date,form,acc,doc,r['reportDate'][i])
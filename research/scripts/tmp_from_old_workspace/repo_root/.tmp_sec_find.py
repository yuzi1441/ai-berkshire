import requests
headers={'User-Agent':'codex-research whatn@example.com'}
data=requests.get('https://data.sec.gov/submissions/CIK0001651308.json',headers=headers,timeout=20).json()
recent=data['filings']['recent']
for form_target in ['10-K','10-Q','DEF 14A','20-F']:
    print('---',form_target)
    n=0
    for i,form in enumerate(recent['form']):
        if form==form_target:
            print(i, recent['filingDate'][i], form, recent['accessionNumber'][i], recent['primaryDocument'][i], recent['primaryDocDescription'][i])
            n+=1
            if n>=10: break

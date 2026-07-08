import requests, re
from bs4 import BeautifulSoup
headers={'User-Agent':'Mozilla/5.0'}
urls=[
'https://ir.beonemedicines.com/news/beigene-announces-fourth-quarter-and-full-year-2024-financial-results-and-business-updates/ae4b526f-e135-4ce7-84fe-e9a8ba557406',
'https://ir.beonemedicines.com/news/beone-medicines-announces-first-quarter-2026-financial-results-and-business-updates',
'https://ir.beonemedicines.com/news'
]
for url in urls:
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print('\nURL',url,'status',r.status_code,'len',len(r.text), 'final', r.url)
        print(r.text[:300])
        soup=BeautifulSoup(r.text,'html.parser')
        print(soup.get_text(' ',strip=True)[:1000])
    except Exception as e: print('ERR',e)

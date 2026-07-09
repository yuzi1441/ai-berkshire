import requests, re, json, pathlib
from bs4 import BeautifulSoup
symbols=['ttmi','rog']
headers={'User-Agent':'Mozilla/5.0'}
out={}
for sym in symbols:
    out[sym]={}
    for page in ['statistics','financials','financials/cash-flow-statement','financials/balance-sheet']:
        url=f'https://stockanalysis.com/stocks/{sym}/{page}/'
        html=requests.get(url,headers=headers,timeout=20).text
        out[sym][page]=html[:200000]
        soup=BeautifulSoup(html,'html.parser')
        title=soup.find('title')
        print('\n',sym,page,title.get_text(strip=True) if title else '')
        text=soup.get_text('\n',strip=True)
        for key in ['Market Cap','PE Ratio','Revenue','Net Income','Operating Cash Flow','Total Liabilities','Shareholders\' Equity','Debt / Equity Ratio','Return on Equity']:
            idx=text.find(key)
            if idx>=0: print(key, text[idx:idx+250].replace('\n',' | '))
pathlib.Path('data/ai-pcb-materials').mkdir(parents=True,exist_ok=True)
pathlib.Path('data/ai-pcb-materials/stockanalysis_us_pages_20260710.json').write_text(json.dumps(out,ensure_ascii=False),encoding='utf-8')

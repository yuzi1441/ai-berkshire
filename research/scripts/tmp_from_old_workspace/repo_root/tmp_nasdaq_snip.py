from pathlib import Path
import requests, re
r=requests.get('https://www.nasdaq.com/market-activity/stocks/onc',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
text=r.text
for term in ['Last Sale','Market Cap','ONC','primaryData','summaryData']:
 idx=text.find(term)
 print('\nTERM',term,idx)
 print(text[idx:idx+1500] if idx!=-1 else '')

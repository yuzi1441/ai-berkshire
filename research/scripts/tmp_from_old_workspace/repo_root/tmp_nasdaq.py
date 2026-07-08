import requests, re
url='https://www.nasdaq.com/market-activity/stocks/onc'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=20)
print(r.status_code, len(r.text), r.text[:100])
for pat in ['Market Cap','Last Sale','data-symbol']:
 print(pat, r.text.find(pat))
print(re.findall(r'\$[0-9,.]+', r.text[:200000])[:20])

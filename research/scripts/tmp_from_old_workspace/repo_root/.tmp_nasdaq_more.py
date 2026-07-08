import requests, json
headers={'User-Agent':'Mozilla/5.0','Accept':'application/json, text/plain, */*','Origin':'https://www.nasdaq.com','Referer':'https://www.nasdaq.com/market-activity/stocks/onc'}
for endpoint in ['summary','info','financials','historical']:
    url=f'https://api.nasdaq.com/api/quote/ONC/{endpoint}?assetclass=stocks'
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print('\n###',endpoint,r.status_code,len(r.text))
        print(r.text[:1000])
        open(f'sources/sec_beone/nasdaq_{endpoint}.json','w',encoding='utf-8').write(r.text)
    except Exception as e: print('ERR',endpoint,e)
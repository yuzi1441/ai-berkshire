import requests, re, json
urls={
'google':'https://www.google.com/finance/quote/688235:SHA',
'googlehk':'https://www.google.com/finance/quote/6160:HKG',
'googleus':'https://www.google.com/finance/quote/ONC:NASDAQ',
'marketwatch':'https://www.marketwatch.com/investing/stock/onc',
'nasdaq':'https://api.nasdaq.com/api/quote/ONC/info?assetclass=stocks',
'eastmoney':'https://push2.eastmoney.com/api/qt/stock/get?secid=1.688235&fields=f43,f57,f58,f116,f117,f162,f167,f168,f170,f169,f46,f44,f45,f60,f48,f49,f152',
'eastmoneyhk':'https://push2.eastmoney.com/api/qt/stock/get?secid=116.06160&fields=f43,f57,f58,f116,f117,f162,f167,f168,f170,f169,f46,f44,f45,f60,f48,f49,f152',
}
headers={'User-Agent':'Mozilla/5.0','Accept':'text/html,application/json'}
for name,url in urls.items():
    try:
        r=requests.get(url,headers=headers,timeout=20)
        print('\n###',name,r.status_code,r.url,'len',len(r.text))
        print(r.text[:500].replace('\n',' ')[:500])
        open(f'sources/sec_beone/{name}_quote_raw.txt','w',encoding='utf-8').write(r.text)
    except Exception as e: print('\nERR',name,type(e).__name__,e)
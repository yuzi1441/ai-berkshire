import json, urllib.request, time
symbols=['ONC','688235.SS','6160.HK']
url='https://query1.finance.yahoo.com/v7/finance/quote?symbols='+','.join(symbols)
try:
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    data=json.loads(urllib.request.urlopen(req, timeout=15).read().decode('utf-8'))
    for r in data['quoteResponse']['result']:
        print(json.dumps({k:r.get(k) for k in ['symbol','regularMarketPrice','regularMarketPreviousClose','regularMarketTime','marketCap','trailingPE','forwardPE','priceToSalesTrailing12Months','currency','shortName','regularMarketChangePercent','regularMarketDayHigh','regularMarketDayLow']}, ensure_ascii=False))
except Exception as e:
    print('ERR', type(e).__name__, e)
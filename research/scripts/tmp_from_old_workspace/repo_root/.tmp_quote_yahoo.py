import json, urllib.request
symbols=['ONC','6160.HK','688235.SS']
url='https://query1.finance.yahoo.com/v7/finance/quote?symbols='+','.join(symbols)
try:
    req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0'})
    data=json.load(urllib.request.urlopen(req, timeout=20))
    print(json.dumps(data, ensure_ascii=False, indent=2)[:5000])
except Exception as e:
    print('ERR',type(e).__name__,e)

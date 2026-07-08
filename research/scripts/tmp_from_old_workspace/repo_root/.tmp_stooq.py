import urllib.request, json, csv, io
for sym in ['onc.us','bgne.us']:
    url=f'https://stooq.com/q/l/?s={sym}&f=sd2t2ohlcv&h&e=csv'
    try:
        txt=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=15).read().decode('utf-8')
        print('URL',url)
        print(txt)
    except Exception as e: print('ERR',sym,e)
import requests
headers={'User-Agent':'Mozilla/5.0'}
urls=[
 'https://api.money.126.net/data/feed/0000400,money.api?callback=_ntes_quote_callback',
 'http://api.money.126.net/data/feed/0000400,money.api?callback=_ntes_quote_callback',
 'https://webquoteklinepic.eastmoney.com/GetPic.aspx?nid=0.000400&type=&unitWidth=-6&ef=&formula=MACD&AT=1&imageType=KXL',
 'https://emweb.securities.eastmoney.com/PC_HSF10/OperationsRequired/Index?type=web&code=SZ000400',
]
for u in urls:
 print('---',u)
 try:
  r=requests.get(u,headers=headers,timeout=15)
  print(r.status_code, r.text[:800] if 'image' not in r.headers.get('content-type','') else r.headers.get('content-type'))
 except Exception as e: print(type(e),e)
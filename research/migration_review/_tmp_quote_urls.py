import requests, sys, json
urls=[
 'https://hq.sinajs.cn/list=sz000682',
 'https://qt.gtimg.cn/q=sz000682',
 'https://web.ifzq.gtimg.cn/appstock/app/fqkline/get?param=sz000682,day,,,5,qfq',
 'https://api-ddc-wscn.awtmt.com/market/kline?prod_code=000682.SZ&tick_count=5&period_type=86400&adjust_price_type=forward'
]
for u in urls:
 print('\nURL',u)
 try:
  r=requests.get(u,timeout=10,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
  print(r.status_code, r.encoding, r.text[:500])
 except Exception as e: print('ERR',repr(e))

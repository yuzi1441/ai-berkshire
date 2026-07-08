import requests
for url in [
 'https://hq.sinajs.cn/list=sz000682',
 'https://qt.gtimg.cn/q=sz000682',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.000682&fields=f43,f57,f58,f116,f117,f162,f167,f168,f169,f170,f46,f44,f45,f60,f85,f84,f173,f187,f105,f183,f184,f185,f186,f188,f189,f190,f191,f192'
]:
 print('\nURL',url)
 try:
  r=requests.get(url,headers={'Referer':'https://finance.sina.com.cn/','User-Agent':'Mozilla/5.0'},timeout=15)
  print(r.status_code, r.encoding, r.text[:1000])
 except Exception as e: print(type(e),e)

import requests
for url in ['https://hq.sinajs.cn/list=sh600900','https://push2.eastmoney.com/api/qt/stock/get?secid=1.600900&fields=f43,f58,f116,f117,f84,f85,f162,f167,f168,f169,f170,f46,f44,f45,f60,f57,f107,f152,f9,f23,f20,f21,f115','https://datacenter.eastmoney.com/securities/api/data/get?type=RPT_F10_FINANCE_GINCOME&sty=APP_F10_GINCOME&filter=(SECUCODE=%22600900.SH%22)&p=1&ps=10']:
 print('URL',url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=15)
  print(r.status_code, r.text[:500])
 except Exception as e: print(type(e).__name__, repr(e))

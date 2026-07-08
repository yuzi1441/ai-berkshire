import requests
urls=[
 'https://qt.gtimg.cn/q=sz002270',
 'https://hq.sinajs.cn/list=sz002270',
 'https://push2.eastmoney.com/api/qt/stock/get?secid=0.002270&fields=f43,f44,f45,f46,f47,f48,f49,f57,f58,f60,f107,f116,f117,f162,f167,f168,f169,f170,f171,f172,f173,f174,f175,f176,f177,f178,f198,f199,f292'
]
for url in urls:
 print('\nURL',url)
 try:
  r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
  print(r.status_code, r.text[:1000])
 except Exception as e: print('ERR',repr(e))

import urllib.request, ssl
urls=[
 ('eastmoney','https://push2.eastmoney.com/api/qt/stock/get?secid=0.002270&fields=f43,f44,f45,f46,f47,f48,f57,f58,f60,f85,f116,f117,f162,f167,f168,f170,f169,f171,f172,f173,f174,f175,f176,f177,f178,f198,f199,f292'),
 ('tencent','https://qt.gtimg.cn/q=sz002270'),
 ('sina','https://hq.sinajs.cn/list=sz002270')
]
for name,url in urls:
 print('\n---',name,'---')
 req=urllib.request.Request(url, headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/'})
 try:
  with urllib.request.urlopen(req, timeout=20, context=ssl._create_unverified_context()) as r:
   data=r.read()
   print(data[:2000].decode('gbk','ignore'))
 except Exception as e:
  print('ERR',repr(e))
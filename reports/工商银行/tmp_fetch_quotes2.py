import requests
urls=[
 'https://qt.gtimg.cn/q=sh601398,hk01398',
 'https://web.sqt.gtimg.cn/q=sh601398,hk01398',
 'https://stock.xueqiu.com/v5/stock/quote.json?symbol=SH601398',
]
headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'}
for u in urls:
 print('\nURL',u)
 try:
  r=requests.get(u,headers=headers,timeout=10)
  print(r.status_code, r.text[:1000])
 except Exception as e:
  print(type(e).__name__, e)
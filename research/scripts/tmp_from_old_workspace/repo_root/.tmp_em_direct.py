import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'https://quote.eastmoney.com/sz002270.html'}
urls=[
('push2','https://push2.eastmoney.com/api/qt/stock/get?secid=0.002270&fields=f43,f57,f58,f60,f46,f44,f45,f47,f48,f50,f116,f117,f162,f167'),
('push2his','https://push2his.eastmoney.com/api/qt/stock/kline/get?secid=0.002270&klt=101&fqt=1&beg=20260706&end=20260706&fields1=f1,f2,f3,f4,f5,f6&fields2=f51,f52,f53,f54,f55,f56,f57,f58')]
for name,url in urls:
 try:
  r=requests.get(url,headers=headers,timeout=20,proxies={'http':None,'https':None})
  print(name,r.status_code,r.text[:1000])
 except Exception as e: print(name,'ERR',repr(e))
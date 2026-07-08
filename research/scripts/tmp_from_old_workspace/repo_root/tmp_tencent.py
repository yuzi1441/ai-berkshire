import requests
for url in ['https://qt.gtimg.cn/q=sz002270','http://qt.gtimg.cn/q=sz002270','https://web.sqt.gtimg.cn/q=sz002270']:
  try:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/sz002270/gp'},timeout=10,proxies={'http':None,'https':None})
    print('URL',url,'status',r.status_code,'encoding',r.encoding)
    print(r.text[:500])
  except Exception as e:
    print('ERR',url,repr(e))

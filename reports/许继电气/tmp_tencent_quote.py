import requests
for url in ['https://qt.gtimg.cn/q=sz000400','http://qt.gtimg.cn/q=sz000400','https://web.sqt.gtimg.cn/q=sz000400']:
  try:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'},timeout=20)
    print('\n',url,r.status_code,r.encoding,r.apparent_encoding,r.text[:400])
  except Exception as e: print('ERR',url,e)
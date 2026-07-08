import requests, json
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=300760'}
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
for stock in ['300760,9900022601','300760,gfbj0834966','300760']:
  data={'stock':stock,'tabName':'fulltext','pageSize':20,'pageNum':1,'column':'szse','plate':'sz','seDate':'2026-01-01~2026-07-06','isHLtitle':'true'}
  r=requests.post(url,data=data,headers=headers)
  print('stock',stock,r.status_code,r.text[:500])

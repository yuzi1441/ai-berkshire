import requests, json
url='http://www.cninfo.com.cn/new/information/topSearch/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
params={'keyWord':'华明装备','maxNum':10}
r=requests.get(url,params=params,headers=headers,timeout=10)
print(r.status_code,r.text[:2000])

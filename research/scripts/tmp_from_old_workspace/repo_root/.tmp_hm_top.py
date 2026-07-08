import requests,json
url='http://www.cninfo.com.cn/new/information/topSearch/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/index'}
r=requests.post(url,data={'keyWord':'华明装备','maxNum':10},headers=headers,timeout=20)
print(r.status_code, r.text[:1000])

import requests, json
url='http://www.cninfo.com.cn/new/information/topSearch/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/index'}
for key in ['工商银行','601398']:
 r=requests.post(url,data={'keyWord':key,'maxNum':'10'},headers=headers,timeout=20); print(key,r.status_code,r.text[:1000])

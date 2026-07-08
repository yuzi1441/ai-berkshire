import requests
urls=['https://qt.gtimg.cn/q=sh601126','https://hq.sinajs.cn/list=sh601126']
for u in urls:
    print('URL',u)
    r=requests.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn'},timeout=20)
    print(r.status_code, r.text[:500])

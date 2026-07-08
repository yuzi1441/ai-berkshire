import requests,re,json,decimal
for code in ['600312','sh600312']:
    pass
url='https://qt.gtimg.cn/q=sh600312'
r=requests.get(url,timeout=15,headers={'User-Agent':'Mozilla/5.0'})
text=r.text
s=text.split('="',1)[1].rsplit('"',1)[0]
fields=s.split('~')
for i,v in enumerate(fields[:70]): print(i, v)

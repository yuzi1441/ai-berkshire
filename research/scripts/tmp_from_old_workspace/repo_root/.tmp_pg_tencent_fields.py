import requests
s=requests.Session(); s.trust_env=False
r=s.get('https://qt.gtimg.cn/q=sh600312',headers={'User-Agent':'Mozilla/5.0'},timeout=15)
text=r.content.decode('gbk','ignore')
body=text.split('=\"',1)[1].rsplit('\"',1)[0]
fields=body.split('~')
for i,v in enumerate(fields):
    print(i, v)

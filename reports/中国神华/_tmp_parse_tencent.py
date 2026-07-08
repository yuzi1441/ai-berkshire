import requests,re
s=requests.get('https://qt.gtimg.cn/q=sh601088',headers={'User-Agent':'Mozilla/5.0'},timeout=15).content.decode('gbk','replace')
inside=s[s.find('"')+1:s.rfind('"')]
vals=inside.split('~')
for i,v in enumerate(vals):
    print(i,repr(v))
import requests,re
r=requests.get('https://qt.gtimg.cn/q=sz000400',headers={'User-Agent':'Mozilla/5.0'},timeout=20)
p=re.search(r'="(.*)"',r.text).group(1).split('~')
for i,v in enumerate(p): print(i,repr(v))

import requests,re
text=requests.get('https://qt.gtimg.cn/q=sz000682',headers={'User-Agent':'Mozilla/5.0'},timeout=15).content.decode('gbk','ignore')
f=re.search(r'"(.*)"',text).group(1).split('~')
for i,x in enumerate(f): print(i,x)

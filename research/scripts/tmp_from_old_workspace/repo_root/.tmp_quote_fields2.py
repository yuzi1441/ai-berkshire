import requests
code='sz002270'
t=requests.get('https://qt.gtimg.cn/q='+code,headers={'User-Agent':'Mozilla/5.0'},timeout=20).text
arr=t.split('="',1)[1].rstrip('";').split('~')
for i,x in enumerate(arr): print(i,repr(x))

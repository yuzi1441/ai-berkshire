import requests
r=requests.get('https://qt.gtimg.cn/q=sh600900,sh600905,sh600025,sh600886',headers={'User-Agent':'Mozilla/5.0'},timeout=15)
print(r.text)

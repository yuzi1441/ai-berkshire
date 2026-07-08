import requests
raw=requests.get('https://qt.gtimg.cn/q=sz002028',headers={'User-Agent':'Mozilla/5.0'},timeout=20).content.decode('gbk')
print(raw)
fields=raw.split(chr(34))[1].split('~')
for i,f in enumerate(fields): print(i,repr(f))
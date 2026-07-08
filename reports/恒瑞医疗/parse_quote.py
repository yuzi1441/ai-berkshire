import urllib.request, json, pathlib, re
url='https://qt.gtimg.cn/q=sh600276'
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
data=urllib.request.urlopen(req,timeout=20).read().decode('gbk')
print(data)
fields=data[data.find('"')+1:data.rfind('"')].split('~')
for idx,val in enumerate(fields):
    print(idx, repr(val))
pathlib.Path('sources/tencent_quote_600276_20260706.txt').write_text(data,encoding='utf-8')
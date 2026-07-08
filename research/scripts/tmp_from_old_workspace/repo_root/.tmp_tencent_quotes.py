import requests, re, json, os, math
codes=['sz002270','sz002028','sz002452','sh600406','sh600089']
url='https://qt.gtimg.cn/q='+','.join(codes)
r=requests.get(url, headers={'User-Agent':'Mozilla/5.0'}, timeout=20)
print(r.status_code, r.encoding, len(r.text))
print(r.text[:1000])
# parse v_sz002270="~华明装备~002270~..."
for part in r.text.split(';'):
    if '~' in part:
        name=part.split('=')[0]
        val=part.split('="',1)[1].rstrip('"') if '="' in part else part
        arr=val.split('~')
        print('\n',name, len(arr))
        for i,x in enumerate(arr[:60]):
            if x: print(i,x)

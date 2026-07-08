import urllib.request, re, json
for q in ['sh601088','hk01088']:
    url=f'http://qt.gtimg.cn/q={q}'
    try:
        data=urllib.request.urlopen(urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'}),timeout=20).read().decode('gbk','ignore')
        print(q, data[:500])
    except Exception as e:
        print(q,'ERR',repr(e))

import urllib.request
for url in ['https://qt.gtimg.cn/q=sh688235','https://qt.gtimg.cn/q=hk06160','https://qt.gtimg.cn/q=usONC']:
    print('\nURL',url)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0'})
        raw=urllib.request.urlopen(req,timeout=20).read()
        for enc in ['gbk','utf-8']:
            try:
                print(raw.decode(enc)[:1500]); break
            except Exception: pass
    except Exception as e:
        print('ERR',type(e).__name__,e)

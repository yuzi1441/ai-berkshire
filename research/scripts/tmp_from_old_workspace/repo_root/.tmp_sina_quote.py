import urllib.request
for url in ['https://hq.sinajs.cn/list=sh688235','https://hq.sinajs.cn/list=hk06160','https://hq.sinajs.cn/list=gb_onc']:
    print('\nURL',url)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'})
        raw=urllib.request.urlopen(req,timeout=20).read()
        for enc in ['gbk','utf-8']:
            try:
                print(raw.decode(enc)[:1500]); break
            except Exception: pass
    except Exception as e:
        print('ERR',type(e).__name__,e)

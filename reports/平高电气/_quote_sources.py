import requests, re, json, os, sys
for k in ['HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','http_proxy','https_proxy','all_proxy']:
    pass
urls = {
 'sina':'https://hq.sinajs.cn/list=sh600312',
 'tencent':'https://qt.gtimg.cn/q=sh600312',
 'netease':'https://api.money.126.net/data/feed/0600312,money.api?callback=_ntes_quote_callback'
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'}
for name,url in urls.items():
    try:
        r=requests.get(url,headers=headers,timeout=15)
        print('\n---',name,r.status_code,r.encoding)
        print(r.text[:1000])
    except Exception as e: print('ERR',name,type(e).__name__,e)

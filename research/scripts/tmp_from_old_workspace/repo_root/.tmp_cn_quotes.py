import requests, re, json
headers={'User-Agent':'Mozilla/5.0'}
urls={
'sina_a':'https://hq.sinajs.cn/list=sh688235',
'sina_hk':'https://hq.sinajs.cn/list=hk06160',
'tencent_a':'https://qt.gtimg.cn/q=sh688235',
'tencent_hk':'https://qt.gtimg.cn/q=hk06160',
'tencent_us':'https://qt.gtimg.cn/q=usONC',
'netease_a':'https://api.money.126.net/data/feed/060688235,money.api?callback=_ntes_quote_callback',
}
for name,url in urls.items():
    try:
        r=requests.get(url,headers=headers,timeout=20)
        r.encoding='gbk' if 'sinajs' in url or 'gtimg' in url else 'utf-8'
        print('\n###',name,r.status_code,len(r.text))
        print(r.text[:1000])
    except Exception as e: print('\nERR',name,type(e).__name__,e)
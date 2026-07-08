import requests, json, re
urls = {
 'eastmoney_quote':'https://push2.eastmoney.com/api/qt/stock/get?secid=0.002028&fields=f43,f57,f58,f169,f170,f46,f44,f45,f60,f116,f117,f162,f167,f168,f47,f48,f152,f71,f122',
 'tencent_quote':'https://qt.gtimg.cn/q=sz002028',
}
for k,u in urls.items():
    print('\n---', k, '---')
    r=requests.get(u, timeout=15, headers={'User-Agent':'Mozilla/5.0'})
    print(r.status_code, r.headers.get('content-type'))
    print(r.content[:500].decode('gbk','ignore') if k=='tencent_quote' else r.text[:1000])

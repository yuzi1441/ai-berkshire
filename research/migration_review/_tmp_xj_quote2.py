import requests, re, json
urls=[
 'https://hq.sinajs.cn/list=sz000400',
 'https://qt.gtimg.cn/q=sz000400',
 'https://web.sqt.gtimg.cn/q=sz000400',
]
for u in urls:
    try:
        r=requests.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
        print('URL',u,'status',r.status_code,'ct',r.headers.get('content-type'))
        print(r.text[:1000])
    except Exception as e: print('ERR',u,repr(e))

import requests, re, json, datetime
urls={
 'sina':'https://hq.sinajs.cn/list=sh600312',
 'tencent':'https://qt.gtimg.cn/q=sh600312',
 'tencent_web':'https://web.sqt.gtimg.cn/q=sh600312',
}
for name,u in urls.items():
    try:
        r=requests.get(u,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=20)
        print('\n',name,r.status_code,r.text[:500])
    except Exception as e: print(name,repr(e))

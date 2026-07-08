import requests
for url in ['https://qt.gtimg.cn/q=sz000682','http://qt.gtimg.cn/q=sz000682','https://web.sqt.gtimg.cn/q=sz000682']:
    try:
        r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://gu.qq.com/'},timeout=10)
        enc='gbk'
        r.encoding=enc
        print('\n',url,r.status_code,r.text[:500])
    except Exception as e: print(url,repr(e))
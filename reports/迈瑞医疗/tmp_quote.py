import requests
for url in ['https://qt.gtimg.cn/q=sz300760','https://hq.sinajs.cn/list=sz300760']:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://finance.sina.com.cn/'},timeout=10)
    print('\nURL',url,'status',r.status_code,'encoding',r.encoding)
    print(r.text[:1000])

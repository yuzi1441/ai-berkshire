import requests,re,json
headers={'User-Agent':'Mozilla/5.0'}
urls=['https://hq.sinajs.cn/list=sh601126','https://hq.sinajs.cn/rn=1751810000&list=sh601126']
for url in urls:
    try:
        r=requests.get(url,headers={**headers,'Referer':'https://finance.sina.com.cn'},timeout=20)
        print(url, r.status_code, r.encoding, r.apparent_encoding, len(r.content))
        print(r.content[:300])
        print(r.content.decode('gbk','replace')[:500])
    except Exception as e: print('err',e)
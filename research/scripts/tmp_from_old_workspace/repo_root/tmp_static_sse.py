import requests
for url in ['http://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf','http://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-03-24/601126_20260324_2K9N.pdf','https://static.sse.com.cn/disclosure/listedinfo/announcement/c/new/2026-04-30/601126_20260430_8ESA.pdf']:
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'},timeout=30)
    print(url, r.status_code, r.headers.get('content-type'), len(r.content), r.content[:5])
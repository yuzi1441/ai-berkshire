import requests, json
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/information/topSearch/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/index'}
for key in ['平高电气','600312']:
    r=s.post(url,data={'keyWord':key,'maxSecNum':10},headers=headers,timeout=20)
    print('key',key,r.status_code,r.text[:1000])

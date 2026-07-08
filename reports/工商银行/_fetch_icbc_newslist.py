import requests, json
url='https://papi.icbc.com.cn/cmspage/columns/webpart/webservice/newsList_en'
params={'columnId':'1438058343653851171','modeFlag':'true','pageNumber':'1','pageSize':'50'}
r=requests.get(url,params=params,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.icbc-ltd.com/en/column/1438058343653851171.html'},timeout=30)
print(r.url, r.status_code, r.headers.get('content-type'), len(r.text), r.text[:200])
open('_icbc_newslist_finreports.json','w',encoding='utf-8').write(r.text)
try:
 js=r.json();
 for item in js.get('data',{}).get('list',[])[:30]:
  print(item.get('publishedDate'), item.get('displayName') or item.get('pageName'), item.get('summary'), item.get('path'))
except Exception as e: print(e)

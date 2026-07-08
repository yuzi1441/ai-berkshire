import urllib.request, urllib.parse, ssl, json
url='http://papi.icbc.com.cn/cmspage/columns/webpart/webservice/newsList_en?'+urllib.parse.urlencode({'columnId':'1438058343653851171','modeFlag':'true','pageNumber':'1','pageSize':'50'})
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.icbc-ltd.com/en/column/1438058343653851171.html'})
with urllib.request.urlopen(req,timeout=30) as r:
    data=r.read().decode('utf-8','replace')
print(url, len(data), data[:200])
open('_icbc_newslist_finreports.json','w',encoding='utf-8').write(data)
js=json.loads(data)
for item in js.get('data',{}).get('list',[])[:50]:
 print(item.get('publishedDate'), item.get('displayName') or item.get('pageName'), item.get('summary'), item.get('path'))

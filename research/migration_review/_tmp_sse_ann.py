import requests, time, json, re
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback123456',
 'isPagination':'true',
 'productId':'688271',
 'securityType':'0101,120100,020100,020200,120200',
 'reportType2':'DQBG',
 'reportType':'ALL',
 'beginDate':'2025-01-01',
 'endDate':'2026-07-06',
 'pageHelp.pageSize':'50',
 'pageHelp.pageNo':'1',
 'pageHelp.beginPage':'1',
 'pageHelp.cacheSize':'1',
 'pageHelp.endPage':'5',
 '_':str(int(time.time()*1000))
}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
r=requests.get(url,params=params,headers=headers,timeout=20)
print(r.url)
print(r.status_code, r.text[:500])
text=re.sub(r'^jsonpCallback\d+\(|\)$','',r.text)
try:
 data=json.loads(text); print(data.keys());
 for row in data.get('result',[])[:20]:
  print(row.get('SSEDATE'), row.get('TITLE'), row.get('URL'))
except Exception as e: print('json err',e, text[:1000])

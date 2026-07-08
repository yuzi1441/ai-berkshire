import requests, time, re, json
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback12345',
 'isPagination':'true',
 'productId':'600900',
 'securityType':'0101',
 'reportType2':'',
 'reportType':'ALL',
 'beginDate':'2025-01-01',
 'endDate':'2026-07-07',
 'pageHelp.pageSize':'50',
 'pageHelp.pageNo':'1',
 'pageHelp.beginPage':'1',
 'pageHelp.cacheSize':'1',
 'pageHelp.endPage':'5',
 '_':str(int(time.time()*1000))}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
r=requests.get(url,params=params,headers=headers,timeout=20)
print(r.status_code,r.text[:500])
text=r.text
m=re.search(r'jsonpCallback12345\((.*)\)$',text)
if m:
 js=json.loads(m.group(1)); print(js.keys());
 for item in js.get('result',[])[:20]:
  print(item.get('SSEDATE'), item.get('TITLE'), item.get('URL'))

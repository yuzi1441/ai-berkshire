import requests, time, re, json, pathlib
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback12345','isPagination':'true','productId':'600900','securityType':'0101',
 'reportType2':'', 'reportType':'ALL','beginDate':'2026-01-01','endDate':'2026-07-07',
 'pageHelp.pageSize':'100','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':str(int(time.time()*1000))}
r=requests.get(url,params=params,headers=headers,timeout=20)
m=re.search(r'jsonpCallback12345\((.*)\)$',r.text); js=json.loads(m.group(1))
items=js.get('result') or js.get('pageHelp',{}).get('data') or []
for item in items:
 title=item.get('TITLE') or item.get('BULLETIN_HEADING')
 if title and any(k in title for k in ['年度报告','第一季度报告','权益分派','发电量']):
  print(item.get('SSEDATE'), title, item.get('URL'))
  full='https://www.sse.com.cn'+item.get('URL')
  fn='reports/长江电力/sources/sse_'+full.split('/')[-1]
  rr=requests.get(full,headers=headers,timeout=30)
  pathlib.Path(fn).write_bytes(rr.content)
  print(' saved',fn,len(rr.content),rr.content[:8])

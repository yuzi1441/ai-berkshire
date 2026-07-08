import requests,time,re,json
s=requests.Session(); headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/'}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
for bd,ed in [('2026-04-01','2026-05-10'),('2026-01-01','2026-07-07')]:
 params={'jsonCallBack':'jsonpCallback12345','isPagination':'true','productId':'600900','securityType':'0101','reportType2':'DQBG','reportType':'ALL','beginDate':bd,'endDate':ed,'pageHelp.pageSize':'100','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':str(int(time.time()*1000))}
 for rt2 in ['DQBG','','YJDBG']:
  params['reportType2']=rt2
  r=s.get(url,params=params,headers=headers,timeout=20)
  m=re.search(r'jsonpCallback12345\((.*)\)$',r.text)
  print('range',bd,ed,'rt2',rt2,'status',r.status_code,'m',bool(m),r.text[:120])
  if m:
   js=json.loads(m.group(1)); items=js.get('result') or js.get('pageHelp',{}).get('data') or []
   print('items',len(items))
   for item in items[:80]:
    title=item.get('TITLE') or ''
    if any(k in title for k in ['季度','一季','报告','年度']):
     print(item.get('SSEDATE'), title, item.get('URL'))

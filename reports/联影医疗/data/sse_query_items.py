import requests, re, json
headers={'Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/','User-Agent':'Mozilla/5.0'}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
for kw in ['第一季度报告','投资者关系活动记录','回购','减持股份结果','部分募投项目延期']:
 params={'jsonCallBack':'jsonpCallback','isPagination':'true','productId':'688271','keyWord':kw,'securityType':'0101','reportType':'ALL','beginDate':'2025-01-01','endDate':'2026-07-06','pageHelp.pageSize':'10','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':'1780000000000'}
 r=requests.get(url,params=params,headers=headers,timeout=20)
 print('\n##',kw,r.status_code)
 txt=r.text
 m=re.search(r'jsonpCallback\((.*)\)$',txt)
 data=json.loads(m.group(1)) if m else {}
 for item in data.get('pageHelp',{}).get('data') or []:
  print(item.get('SSEDATE'), item.get('TITLE'), 'https://www.sse.com.cn'+item.get('URL',''))

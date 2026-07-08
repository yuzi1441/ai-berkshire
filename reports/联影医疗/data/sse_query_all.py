import requests, re, json
headers={'Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/','User-Agent':'Mozilla/5.0'}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={'jsonCallBack':'jsonpCallback','isPagination':'true','productId':'688271','keyWord':'','securityType':'0101','reportType':'ALL','beginDate':'2026-04-25','endDate':'2026-05-05','pageHelp.pageSize':'50','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5','_':'1780000000000'}
r=requests.get(url,params=params,headers=headers,timeout=20)
print(r.status_code, r.text[:500])
m=re.search(r'jsonpCallback\((.*)\)$',r.text)
data=json.loads(m.group(1))
print('total',data['pageHelp'].get('total'))
for item in data['pageHelp'].get('data') or []:
 print(item.get('SSEDATE'), item.get('TITLE'), 'https://www.sse.com.cn'+item.get('URL',''))

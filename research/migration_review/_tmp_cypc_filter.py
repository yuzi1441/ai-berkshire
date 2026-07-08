import requests, time, json, re
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do'
params={
 'jsonCallBack':'jsonpCallback123456','isPagination':'true','productId':'600900',
 'securityType':'0101,120100,020100,020200,120200','reportType':'ALL',
 'beginDate':'2025-01-01','endDate':'2026-07-07','pageHelp.pageSize':'200','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'10','_':str(int(time.time()*1000))}
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/'}
r=requests.get(url,params=params,headers=headers,timeout=20)
text=re.sub(r'^jsonpCallback\d+\(|\)$','',r.text)
data=json.loads(text)
rows=data.get('pageHelp',{}).get('data') or data.get('result',[])
print('rows', len(rows))
for row in rows:
    title=row.get('TITLE','')
    if any(k in title for k in ['2025年年度报告','2026年第一季度报告','发电量完成情况公告','环境、社会','分红','利润分配','年度股东会资料']):
        print(row.get('SSEDATE'), title, 'https://www.sse.com.cn'+row.get('URL',''))
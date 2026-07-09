import urllib.request, urllib.parse, json
params={'isPagination':'true','productId':'600420','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'','reportType':'ALL','beginDate':'2024-01-01','endDate':'2026-07-08','pageHelp.pageSize':'200','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5'}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?'+urllib.parse.urlencode(params)
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/index.shtml?productId=600420','Accept':'application/json,*/*'})
data=json.loads(urllib.request.urlopen(req,timeout=20).read().decode('utf-8'))
rows=data['pageHelp']['data']
print('total', data['pageHelp'].get('total'), 'rows', len(rows))
for r in rows[:80]:
    if any(k in r['TITLE'] for k in ['年度报告','一季度','半年度','董事','监事','股东','利润分配','分红','关联交易','募集','减值','担保','药品','合规','激励','限制性股票','财务','审计','环境']):
        print(r['SSEDATE'], r['TITLE'], 'https://www.sse.com.cn'+r['URL'])

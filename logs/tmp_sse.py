import urllib.request, urllib.parse, json
params={
'isPagination':'true','productId':'600420','keyWord':'','securityType':'0101,120100,020100,020200,120200','reportType2':'','reportType':'ALL','beginDate':'2026-01-01','endDate':'2026-07-08','pageHelp.pageSize':'50','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5'
}
url='https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?'+urllib.parse.urlencode(params)
req=urllib.request.Request(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/index.shtml?productId=600420','Accept':'application/json,*/*'})
raw=urllib.request.urlopen(req,timeout=20).read()
print(raw[:500])
print(raw.decode('utf-8')[:3000])

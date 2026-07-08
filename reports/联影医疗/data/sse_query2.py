import requests, json, re
headers={'Referer':'https://www.sse.com.cn/disclosure/listedinfo/announcement/','User-Agent':'Mozilla/5.0'}
base='https://query.sse.com.cn/security/stock/queryCompanyBulletinNew.do'
params={
 'jsonCallBack':'jsonpCallback',
 'isPagination':'true',
 'productId':'688271',
 'keyWord':'年度报告',
 'securityType':'0101,120100,020100,020200,120200',
 'reportType2':'',
 'reportType':'ALL',
 'beginDate':'2026-04-01',
 'endDate':'2026-05-10',
 'pageHelp.pageSize':'25','pageHelp.pageNo':'1','pageHelp.beginPage':'1','pageHelp.cacheSize':'1','pageHelp.endPage':'5',
 '_':'1780000000000'
}
for url in [base,'https://query.sse.com.cn/security/stock/queryCompanyBulletin.do','https://query.sse.com.cn/commonQuery.do']:
    try:
        r=requests.get(url,params=params,headers=headers,timeout=20)
        print('\nURL',url,'status',r.status_code,'len',len(r.text))
        print(r.text[:2000])
    except Exception as e: print('ERR',url,e)

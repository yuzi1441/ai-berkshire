import requests, json, re, sys
s=requests.Session(); s.trust_env=False
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.sse.com.cn/assortment/stock/list/info/announcement/'}
urls=[
('sse_list','https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?jsonCallBack=jsonpCallback&isPagination=true&productId=601126&keyWord=&securityType=0101,120100,020100,020200,120200&reportType2=DQBG&reportType=ALL&beginDate=2026-01-01&endDate=2026-07-07&pageHelp.pageSize=25&pageHelp.pageCount=50&pageHelp.pageNo=1&pageHelp.beginPage=1&pageHelp.cacheSize=1&pageHelp.endPage=5'),
('sse_list2','https://query.sse.com.cn/security/stock/queryCompanyBulletin.do?isPagination=true&productId=601126&reportType2=DQBG&beginDate=2026-01-01&endDate=2026-07-07&pageHelp.pageSize=25&pageHelp.pageNo=1'),
]
for name,url in urls:
 try:
  r=s.get(url,headers=headers,timeout=20)
  print('\n---',name,r.status_code,r.url)
  print(r.text[:3000])
 except Exception as e: print('ERR',name,type(e).__name__,e)
# cninfo query try with orgid search
headers2={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/disclosure/stock?stockCode=601126'}
for stock in ['601126,gssh0601126','601126,9900014114','601126']:
 data={'stock':stock,'tabName':'fulltext','pageSize':'30','pageNum':'1','column':'sse','category':'category_ndbg_szsh;category_yjdbg_szsh;','plate':'sh','seDate':'2026-01-01~2026-07-07','searchkey':''}
 try:
  r=s.post('https://www.cninfo.com.cn/new/hisAnnouncement/query',data=data,headers=headers2,timeout=20)
  print('\n--- cninfo',stock,r.status_code)
  print(r.text[:3000])
 except Exception as e: print('ERR cninfo',stock,type(e).__name__,e)

import requests, json, re
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search&checkedCategory=category_ndbg_szsh'}
data={
 'pageNum':'1','pageSize':'30','column':'sse','tabName':'fulltext','plate':'sse','stock':'600312,gssh0600312','searchkey':'2026 第一季度报告','secid':'','category':'category_yjdbg_szsh','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post(url,headers=headers,data=data,timeout=20)
print(r.status_code, r.text[:500])
try:
 j=r.json();
 for ann in j.get('announcements') or []:
  print(ann.get('announcementTitle'), ann.get('adjunctUrl'), ann.get('announcementTime'))
except Exception as e: print(e)

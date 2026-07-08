import requests, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'pageNum':1,'pageSize':100,'column':'sse','tabName':'fulltext','plate':'sse','stock':'600276,gssh0600276','searchkey':'2026年第一季度报告','seDate':'2026-04-01~2026-04-30','isHLtitle':'true'}
js=requests.post(url,headers=headers,data=data,timeout=20).json()
for ann in js.get('announcements',[]):
    print(ann['announcementTime'], ann['announcementTitle'], ann['announcementId'], ann['adjunctUrl'])

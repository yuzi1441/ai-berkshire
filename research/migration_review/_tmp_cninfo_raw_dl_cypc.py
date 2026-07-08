import requests, pandas as pd, json, pathlib, re
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
payload={
 'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'','stock':'600900,gssh0600900','searchkey':'','secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search&lastPage=index'})
r=s.post(url,data=payload,timeout=30)
print(r.status_code, r.text[:200])
j=r.json(); anns=j['announcements']
for a in anns[:15]:
    print(a.get('announcementTitle'), a.get('announcementId'), a.get('adjunctUrl'), a.keys())
path=pathlib.Path('data/长江电力/cninfo_raw_2026.json'); path.write_text(json.dumps(j,ensure_ascii=False,indent=2),encoding='utf-8')
# download selected PDFs
sel_titles=['第七届董事会第一次会议决议公告','第七届董事会第二次会议决议公告','2026年第一次临时股东会决议公告','关于董事会换届选举的公告','2026年半年度发电量完成情况公告','2025年度利润分配方案公告']
for a in anns:
    title=re.sub('<.*?>','',a.get('announcementTitle',''))
    if any(k in title for k in sel_titles):
        adj=a.get('adjunctUrl')
        dl='http://static.cninfo.com.cn/'+adj if adj else None
        if dl:
            fname=re.sub(r'[\\/:*?"<>|]+','_',title)+'_'+str(a.get('announcementId'))+'.pdf'
            p=pathlib.Path('data/长江电力')/fname
            rr=s.get(dl,timeout=30)
            print('DL', title, rr.status_code, len(rr.content), p.name)
            if rr.status_code==200: p.write_bytes(rr.content)

import requests, pathlib, re, json, math
s=requests.Session(); s.headers.update({'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search&lastPage=index'})
def query(start,end,keyword='',category=''):
    payload={'pageNum':'1','pageSize':'30','column':'szse','tabName':'fulltext','plate':'','stock':'600900,gssh0600900','searchkey':keyword,'secid':'','category':category,'trade':'','seDate':f'{start}~{end}','sortName':'','sortType':'','isHLtitle':'true'}
    r=s.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',data=payload,timeout=30); r.raise_for_status(); j=r.json(); return j.get('announcements') or []
anns=query('2024-01-01','2025-12-31')+query('2023-01-01','2023-12-31')
sel=[]
for a in anns:
    title=re.sub('<.*?>','',a.get('announcementTitle',''))
    if any(k in title for k in ['2024年年度报告','2023年年度报告','2024年度利润分配','2023年度利润分配','2025年度利润分配','发电量完成情况公告','增持股份计划','增持计划进展','转让清能集团','投资建设','抽水蓄能','股权收购']):
        sel.append(a)
print('sel',len(sel))
for a in sel[:100]: print(a.get('announcementTime'), re.sub('<.*?>','',a.get('announcementTitle','')), a.get('adjunctUrl'))
out=pathlib.Path('data/长江电力'); out.mkdir(parents=True,exist_ok=True)
for a in sel:
    title=re.sub('<.*?>','',a.get('announcementTitle',''))
    if any(k in title for k in ['2024年年度报告','2023年年度报告','2024年度利润分配','2023年度利润分配','增持股份计划','增持计划进展','转让清能集团股权','投资建设河南巩义','投资建设江西寻乌','发电量完成情况公告']):
        adj=a.get('adjunctUrl')
        if adj:
            fname=re.sub(r'[\\/:*?"<>|]+','_',title)+'_'+str(a.get('announcementId'))+'.pdf'
            p=out/fname
            if not p.exists():
                rr=s.get('http://static.cninfo.com.cn/'+adj,timeout=30)
                print('DL',title,rr.status_code,len(rr.content),fname)
                if rr.status_code==200: p.write_bytes(rr.content)
path=out/'cninfo_selected_2023_2025.json'; path.write_text(json.dumps(sel,ensure_ascii=False,indent=2),encoding='utf-8')

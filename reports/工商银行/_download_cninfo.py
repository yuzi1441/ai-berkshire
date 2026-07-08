import requests, pathlib, re
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'}
out=pathlib.Path('sources'); out.mkdir(exist_ok=True)
# query cninfo announcements for 601398 annual reports
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
for page in range(1,3):
    data={
        'pageNum':str(page),'pageSize':'30','column':'sse','tabName':'fulltext','plate':'','stock':'601398,gsyh','searchkey':'年度报告','secid':'','category':'category_ndbg_szsh','trade':'','seDate':'2023-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
    }
    r=requests.post(url,data=data,headers=headers,timeout=30)
    print('page',page,r.status_code,len(r.text),r.text[:80])
    js=r.json()
    for ann in js.get('announcements') or []:
        title=re.sub('<.*?>','',ann.get('announcementTitle',''))
        adjunct=ann.get('adjunctUrl')
        date=ann.get('announcementTime')
        print(title, date, adjunct)
        if '年度报告' in title and '摘要' not in title and adjunct:
            pdfurl='http://static.cninfo.com.cn/'+adjunct
            fname='CNINFO_'+title.replace('/','_').replace(':','_')+'.pdf'
            f=out/fname
            if not f.exists() or f.stat().st_size<10000:
                pr=requests.get(pdfurl,headers=headers,timeout=60)
                print('  dl',pr.status_code,len(pr.content),pr.headers.get('content-type'))
                f.write_bytes(pr.content)

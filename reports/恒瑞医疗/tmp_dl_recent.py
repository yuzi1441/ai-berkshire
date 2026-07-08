import requests, os
from pathlib import Path
base='https://static.cninfo.com.cn/'
ids=['1225405467','1225405466','1225405460','1225388550','1225388513','1225388509','1225383767','1225380471','1225373923','1225373316','1225373310','1225359885','1225335039','1225335036','1225330520','1225330505']
# get announcements json again
import requests
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
data={'pageNum':1,'pageSize':60,'column':'sse','tabName':'fulltext','plate':'sse','stock':'600276,gssh0600276','searchkey':'','seDate':'2026-05-01~2026-07-06','isHLtitle':'true'}
js=requests.post(url,headers=headers,data=data,timeout=20).json()
out=Path('source_pdfs/cninfo_recent'); out.mkdir(parents=True,exist_ok=True)
for ann in js['announcements']:
    aid=ann['announcementId']
    if aid in ids:
        fname=f"{ann['announcementTime']}_{aid}_{ann['announcementTitle'][:30].replace('/','_')}.pdf"
        p=out/fname
        if not p.exists():
            r=requests.get(base+ann['adjunctUrl'],headers=headers,timeout=30)
            p.write_bytes(r.content)
        print(aid, ann['announcementTitle'], ann['adjunctUrl'], p.name, p.stat().st_size)

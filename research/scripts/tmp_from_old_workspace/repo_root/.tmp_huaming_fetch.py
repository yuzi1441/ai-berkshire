import requests, json, pathlib, time
from urllib.parse import urljoin
root=pathlib.Path(r'C:\Users\whatn\Desktop\vibecoding\codex\投资分析\ai-berkshire')
out=root/'sources'/'huaming'
out.mkdir(parents=True, exist_ok=True)
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
def query(searchkey='', category='', seDate=''):
    url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
    data={'stock':'002270,9900005198','searchkey':searchkey,'plate':'szse','category':category,'pageNum':'1','pageSize':'50','column':'szse','tabName':'fulltext','sortName':'','sortType':'','limit':'','seDate':seDate}
    r=requests.post(url,headers=headers,data=data,timeout=30)
    print('query',searchkey,category,seDate,r.status_code,len(r.text))
    r.raise_for_status()
    return r.json().get('announcements') or []
items=[]
for sk,cat,date in [
    ('年度报告','category_ndbg_szsh;',''),
    ('一季度报告','category_yjdbg_szsh;',''),
    ('半年度报告','category_bndbg_szsh;',''),
    ('股权激励','',''),
    ('减持','',''),
    ('监管函','',''),
    ('问询函','',''),
    ('诉讼','',''),
    ('处罚','',''),
    ('分红','',''),
    ('回购','',''),
    ('并购','',''),
    ('业绩承诺','',''),
    ('投资者关系活动记录表','','2023-01-01~2026-07-06'),
]:
    try: items.extend(query(sk,cat,date))
    except Exception as e: print('ERR',sk,e)
# dedup
seen={};
for it in items: seen[it['announcementId']]=it
items=list(seen.values())
(out/'cninfo_announcements.json').write_text(json.dumps(items,ensure_ascii=False,indent=2),encoding='utf-8')
print('items',len(items))
for it in sorted(items,key=lambda x:x['announcementTime'], reverse=True)[:80]:
    print(it['announcementTime'], it['announcementTitle'], it['adjunctUrl'])
# download key reports and selected announcement PDFs
for it in items:
    title=it['announcementTitle']
    if any(k in title for k in ['2025年年度报告','2026年第一季度报告','2025年一季度报告','2024年年度报告','2023年年度报告','2022年年度报告','2021年年度报告','限制性股票激励计划','股权激励','回购','分红','减持','问询','监管','业绩承诺','重大资产','收购','投资者关系活动记录表']):
        url='https://static.cninfo.com.cn/'+it['adjunctUrl']
        safe=''.join(c if c.isalnum() or c in '-_.' else '_' for c in (it['announcementId']+'_'+title))[:150]+'.PDF'
        p=out/safe
        if not p.exists():
            rr=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/'},timeout=60)
            print('download',title,rr.status_code,len(rr.content),url)
            if rr.status_code==200 and rr.content[:4]==b'%PDF': p.write_bytes(rr.content)
            time.sleep(0.2)
print('done',out)

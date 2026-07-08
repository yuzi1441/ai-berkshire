import requests, json, datetime
s=requests.Session(); s.trust_env=False
url='https://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.cninfo.com.cn/new/disclosure/stock?stockCode=600312&orgId=gssh0600312'}
for seDate in ['2024-01-01~2025-12-31','2022-01-01~2024-12-31','2020-01-01~2022-12-31']:
    data={'stock':'600312,gssh0600312','tabName':'fulltext','pageSize':'30','pageNum':'1','column':'sse','category':'category_ndbg_szsh;category_yjdbg_szsh;category_bndbg_szsh;category_yjdbg_szsh;category_yjdbg_szsh;','plate':'sh','seDate':seDate,'searchkey':'年度报告'}
    r=s.post(url,data=data,headers=headers,timeout=20)
    print('---',seDate,r.status_code,'---')
    j=r.json()
    for a in j.get('announcements') or []:
        print(a['announcementTime'], a['announcementTitle'], a['announcementId'], a['adjunctUrl'], a['adjunctSize'])

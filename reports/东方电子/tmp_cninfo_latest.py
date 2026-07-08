import requests, datetime, json
url='http://www.cninfo.com.cn/new/hisAnnouncement/query'
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/disclosure/stock?stockCode=000682&orgId=gssz0000682'}
for key in ['', '处罚', '监管', '诉讼', '仲裁', '问询函', '关注函', '立案', '担保', '关联交易', '分红', '回购', '业绩预告']:
    data={'pageNum':1,'pageSize':30,'column':'szse','tabName':'fulltext','plate':'sz','stock':'000682,gssz0000682','searchkey':key,'secid':'','category':'','trade':'','seDate':'2026-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'}
    js=requests.post(url,headers=headers,data=data,timeout=20).json()
    print('\nKEY=',key or 'ALL','total',js.get('totalAnnouncement'))
    for a in (js.get('announcements') or [])[:12]:
        dt=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
        print(dt, a['announcementTitle'], a['adjunctUrl'])

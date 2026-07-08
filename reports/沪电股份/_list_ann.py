import json, datetime
j=json.load(open('cninfo_2026_announcements.json',encoding='utf-8-sig'))
for a in j.get('announcements') or []:
    t=datetime.datetime.fromtimestamp(a['announcementTime']/1000).strftime('%Y-%m-%d')
    title=a['announcementTitle'].replace('<em>','').replace('</em>','')
    print(t, title, a['adjunctUrl'])

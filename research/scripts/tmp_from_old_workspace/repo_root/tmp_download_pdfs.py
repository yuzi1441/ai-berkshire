import requests, pathlib, json
base='http://static.cninfo.com.cn/'
j=json.load(open('tmp_cninfo.json',encoding='utf-8'))
out=pathlib.Path('data_sources')
out.mkdir(exist_ok=True)
for a in j['announcements']:
    url=base+a['adjunctUrl']
    fn=out/(a['announcementTitle'].replace('/','_')+'.pdf')
    print('download', url, '->', fn)
    r=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
    print(r.status_code, len(r.content), r.headers.get('content-type'))
    fn.write_bytes(r.content)
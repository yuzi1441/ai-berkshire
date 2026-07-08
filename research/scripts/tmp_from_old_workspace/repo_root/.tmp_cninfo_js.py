import requests, re
s=requests.Session(); s.trust_env=False
js=s.get('http://static.cninfo.com.cn/new/assets/js/index.js?v=20260124055940', headers={'User-Agent':'Mozilla/5.0'}, timeout=20).text
open('data/cninfo_index_js.txt','w',encoding='utf-8').write(js)
print('len',len(js))
for pat in ['noticeDownload','announcementId','download','PDF','getDetail','notice']:
 print('PAT',pat,js.find(pat))
 idx=js.find(pat)
 print(js[max(0,idx-500):idx+1000] if idx!=-1 else '')

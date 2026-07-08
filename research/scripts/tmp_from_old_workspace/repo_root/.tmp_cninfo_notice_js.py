import requests, re
s=requests.Session(); s.trust_env=False
js=s.get('http://static.cninfo.com.cn/new/assets/js/disclosure/notice-detail.js?v=20250813091155', headers={'User-Agent':'Mozilla/5.0'}, timeout=20).text
open('data/cninfo_notice_detail_js.txt','w',encoding='utf-8').write(js)
print('len',len(js))
for pat in ['noticeDownload','announcementId','download','adjunctUrl','getDetail','api/announcement','pdfUrl','finalpage']:
 print('\nPAT',pat,js.find(pat))
 idx=js.find(pat)
 print(js[max(0,idx-800):idx+1600] if idx!=-1 else '')

import requests, pathlib, json, re, time
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search'}
# query annual reports 2021-2025
data={
 'pageNum':1,'pageSize':50,'column':'sse','tabName':'fulltext','plate':'','stock':'600312,gssh0600312','searchkey':'','secid':'','category':'category_ndbg_szsh;','trade':'','seDate':'2022-01-01~2026-07-07','sortName':'','sortType':'','isHLtitle':'true'
}
r=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=20)
print(r.status_code)
j=r.json(); anns=j.get('announcements',[])
for a in anns:
 print(a['announcementTime'], a['announcementTitle'], a['adjunctUrl'])
out=pathlib.Path('sources/pinggao'); out.mkdir(parents=True,exist_ok=True)
for a in anns:
 title=a['announcementTitle']
 if '年度报告' in title and '摘要' not in title:
  year=re.search(r'(20\d{2})年年度报告',title).group(1)
  p=out/f'annual{year}.pdf'
  if p.exists() and p.stat().st_size>1000: continue
  url='http://static.cninfo.com.cn/'+a['adjunctUrl']
  rr=requests.get(url,headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/'},timeout=30)
  print('download',year,rr.status_code,len(rr.content),rr.content[:4])
  p.write_bytes(rr.content)
  time.sleep(0.2)

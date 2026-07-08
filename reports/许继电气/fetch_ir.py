import requests, re, pdfplumber
from pathlib import Path
# try sina id page to discover PDF? save html
url='https://money.finance.sina.com.cn/corp/view/vCB_AllBulletinDetail.php?id=12102870&stockid=000400'
r=requests.get(url,headers={'User-Agent':'Mozilla/5.0'},timeout=30)
print('sina',r.status_code,len(r.content),r.encoding,r.apparent_encoding)
text=r.content.decode('gbk','ignore')
Path('sina_ir_20260416.html').write_text(text,encoding='utf-8')
print(text[:500])
# search cninfo by title date
headers={'User-Agent':'Mozilla/5.0','Referer':'http://www.cninfo.com.cn/new/commonUrl/pageOfSearch?url=disclosure/list/search','X-Requested-With':'XMLHttpRequest'}
data={'pageNum':'1','pageSize':'20','column':'szse','tabName':'fulltext','plate':'sz','stock':'000400,gssz0000400','searchkey':'投资者关系活动记录表 2026年4月16日','secid':'','category':'','trade':'','seDate':'2026-04-01~2026-04-30','sortName':'','sortType':'','isHLtitle':'true'}
r2=requests.post('http://www.cninfo.com.cn/new/hisAnnouncement/query',headers=headers,data=data,timeout=20)
print('cninfo',r2.status_code,r2.text[:1000])